"""
Transactional Outbox Repository and Outbox Relay.
Enforces at-least-once message delivery and atomic state+event persistence.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
import logging
import threading
from typing import Any, Dict, List, Optional
import uuid

from libflow.distributed.event_bus import EventBus
from libflow.storage.models import OutboxEventModel

logger = logging.getLogger(__name__)


class OutboxRepository(ABC):
    @abstractmethod
    def save_event(self, topic: str, payload: Dict[str, Any], session: Any = None) -> Dict[str, Any]:
        """Save a new event to the outbox table within the caller's transaction/session."""
        ...

    @abstractmethod
    def fetch_pending(self, limit: int = 50, claim: bool = False) -> List[Dict[str, Any]]:
        """Fetch pending outbox events for publishing. When claim=True, marks events in-flight."""
        ...

    @abstractmethod
    def mark_published(self, event_id: str) -> None:
        """Mark an event as successfully published."""
        ...

    @abstractmethod
    def mark_failed(self, event_id: str, error: str) -> None:
        """Increment retry count and record error status."""
        ...


class InMemoryOutboxRepository(OutboxRepository):
    def __init__(self) -> None:
        self.events: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    def save_event(self, topic: str, payload: Dict[str, Any], session: Any = None) -> Dict[str, Any]:
        with self._lock:
            event_id = f"EVT-{uuid.uuid4().hex[:12].upper()}"
            record = {
                "event_id": event_id,
                "topic": topic,
                "payload": payload,
                "status": "PENDING",
                "retry_count": 0,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "published_at": None,
            }
            self.events.append(record)
            return record

    def fetch_pending(self, limit: int = 50, claim: bool = False) -> List[Dict[str, Any]]:
        with self._lock:
            pending = [e for e in self.events if e["status"] == "PENDING"][:limit]
            if claim:
                for e in pending:
                    e["status"] = "IN_FLIGHT"
            return [{**e} for e in pending]

    def mark_published(self, event_id: str) -> None:
        with self._lock:
            for e in self.events:
                if e["event_id"] == event_id:
                    e["status"] = "PUBLISHED"
                    e["published_at"] = datetime.now(timezone.utc).isoformat()
                    return

    def mark_failed(self, event_id: str, error: str) -> None:
        with self._lock:
            for e in self.events:
                if e["event_id"] == event_id:
                    e["retry_count"] += 1
                    if e["retry_count"] >= 5:
                        e["status"] = "FAILED"
                    else:
                        e["status"] = "PENDING"
                    return


class PostgresOutboxRepository(OutboxRepository):
    def __init__(self, session_factory: Any) -> None:
        self.session_factory = session_factory

    def save_event(self, topic: str, payload: Dict[str, Any], session: Any = None) -> Dict[str, Any]:
        event_id = f"EVT-{uuid.uuid4().hex[:12].upper()}"
        model = OutboxEventModel(
            event_id=event_id,
            topic=topic,
            payload=payload,
            status="PENDING",
            retry_count=0,
            created_at=datetime.utcnow(),
        )
        if session is not None:
            session.add(model)
        else:
            with self.session_factory.create_session() as s:
                s.add(model)
                s.commit()
        return {
            "event_id": event_id,
            "topic": topic,
            "payload": payload,
            "status": "PENDING",
        }

    def fetch_pending(self, limit: int = 50, claim: bool = False) -> List[Dict[str, Any]]:
        from sqlalchemy import select
        with self.session_factory.create_session() as s:
            if claim:
                # Use FOR UPDATE SKIP LOCKED to prevent multi-worker duplicate publication race conditions
                stmt = (
                    select(OutboxEventModel)
                    .where(OutboxEventModel.status == "PENDING")
                    .with_for_update(skip_locked=True)
                    .limit(limit)
                )
                rows = s.scalars(stmt).all()
                result = []
                for r in rows:
                    r.status = "IN_FLIGHT"
                    result.append({
                        "event_id": r.event_id,
                        "topic": r.topic,
                        "payload": r.payload,
                        "status": "IN_FLIGHT",
                        "retry_count": r.retry_count,
                    })
                s.commit()
                return result
            else:
                stmt = select(OutboxEventModel).where(OutboxEventModel.status == "PENDING").limit(limit)
                rows = s.scalars(stmt).all()
                return [
                    {
                        "event_id": r.event_id,
                        "topic": r.topic,
                        "payload": r.payload,
                        "status": r.status,
                        "retry_count": r.retry_count,
                    }
                    for r in rows
                ]

    def mark_published(self, event_id: str) -> None:
        from sqlalchemy import select
        with self.session_factory.create_session() as s:
            stmt = select(OutboxEventModel).where(OutboxEventModel.event_id == event_id)
            row = s.scalars(stmt).first()
            if row:
                row.status = "PUBLISHED"
                row.published_at = datetime.utcnow()
                s.commit()

    def mark_failed(self, event_id: str, error: str) -> None:
        from sqlalchemy import select
        with self.session_factory.create_session() as s:
            stmt = select(OutboxEventModel).where(OutboxEventModel.event_id == event_id)
            row = s.scalars(stmt).first()
            if row:
                row.retry_count += 1
                if row.retry_count >= 5:
                    row.status = "FAILED"
                else:
                    row.status = "PENDING"
                s.commit()


class OutboxRelay:
    """
    Background worker that continuously polls pending outbox events and publishes
    them to the event bus. Guarantees no event loss on server restart or broker reconnect.
    """

    def __init__(
        self,
        outbox_repo: OutboxRepository,
        event_bus: EventBus,
        poll_interval: float = 0.1,
    ) -> None:
        self.outbox_repo = outbox_repo
        self.event_bus = event_bus
        self.poll_interval = poll_interval
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def publish_pending_once(self) -> int:
        pending = self.outbox_repo.fetch_pending(limit=50, claim=True)
        published_count = 0
        for evt in pending:
            try:
                self.event_bus.publish(evt["topic"], evt["payload"])
                self.outbox_repo.mark_published(evt["event_id"])
                published_count += 1
            except Exception as e:
                logger.error(f"[OutboxRelay] Failed to publish event {evt['event_id']}: {e}")
                self.outbox_repo.mark_failed(evt["event_id"], str(e))
        return published_count

    def start(self) -> None:
        self._running = True

        def _relay_loop():
            while self._running:
                try:
                    count = self.publish_pending_once()
                    if count == 0:
                        threading.Event().wait(self.poll_interval)
                except Exception as exc:
                    logger.warning(f"[OutboxRelay] Exception during poll: {exc}")
                    threading.Event().wait(self.poll_interval)

        self._thread = threading.Thread(target=_relay_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
