"""
Distributed Event Backbone & Message Broker
Supports both in-memory pub/sub (for local dev & fast tests) and Redis Streams
(XADD, XREADGROUP, XACK) for distributed, reliable, decoupled event processing across replicas.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections import defaultdict
import json
import logging
import threading
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class EventBus(ABC):
    """Abstract interface for pub/sub message brokers."""

    @abstractmethod
    def publish(self, topic: str, payload: Dict[str, Any]) -> str:
        """Publish an event to a topic. Returns event/message ID."""
        ...

    @abstractmethod
    def subscribe(self, topic: str, handler: Callable[[Dict[str, Any]], None]) -> None:
        """Subscribe a callback to a topic."""
        ...


class InMemoryEventBus(EventBus):
    """Thread-safe in-memory pub/sub message bus."""

    def __init__(self) -> None:
        self._subscribers: Dict[str, List[Callable[[Dict[str, Any]], None]]] = defaultdict(list)
        self._lock = threading.Lock()
        self.published_events_history: List[Dict[str, Any]] = []

    def subscribe(self, topic: str, handler: Callable[[Dict[str, Any]], None]) -> None:
        with self._lock:
            self._subscribers[topic].append(handler)

    def publish(self, topic: str, payload: Dict[str, Any]) -> str:
        with self._lock:
            handlers = list(self._subscribers.get(topic, []))
            self.published_events_history.append({"topic": topic, "payload": payload})

        for handler in handlers:
            try:
                handler(payload)
            except Exception as e:
                logger.error(f"[InMemoryEventBus] Error in handler for topic {topic}: {e}", exc_info=True)
        return f"mem-{len(self.published_events_history)}"


# Backward compatibility alias
DistributedEventBus = InMemoryEventBus


class RedisStreamsEventBus(EventBus):
    """
    Production-ready distributed event bus backed by Redis Streams.
    Provides persistence, consumer groups, replayability, and horizontal scalability.
    """

    def __init__(
        self,
        redis_client: Any,
        stream_prefix: str = "stream:",
        group_name: str = "libraflow_workers",
    ) -> None:
        self.client = redis_client
        self.stream_prefix = stream_prefix
        self.group_name = group_name
        self._subscribers: Dict[str, List[Callable[[Dict[str, Any]], None]]] = defaultdict(list)
        self._lock = threading.Lock()
        self._running = False
        self._consumer_thread: Optional[threading.Thread] = None

    def _stream_key(self, topic: str) -> str:
        return f"{self.stream_prefix}{topic}"

    def publish(self, topic: str, payload: Dict[str, Any]) -> str:
        stream_key = self._stream_key(topic)
        data = {"payload": json.dumps(payload, default=str)}
        try:
            msg_id = self.client.xadd(stream_key, data)
            return msg_id.decode() if isinstance(msg_id, bytes) else str(msg_id)
        except Exception as e:
            logger.error(f"[RedisStreamsEventBus] Failed to publish to {stream_key}: {e}")
            raise

    def subscribe(self, topic: str, handler: Callable[[Dict[str, Any]], None]) -> None:
        stream_key = self._stream_key(topic)
        with self._lock:
            self._subscribers[topic].append(handler)
            try:
                self.client.xgroup_create(stream_key, self.group_name, id="0", mkstream=True)
            except Exception:
                pass

        if not self._running:
            self.start_consumer()

    def start_consumer(self, consumer_name: str = "worker-1") -> None:
        self._running = True

        def _consume_loop():
            while self._running:
                with self._lock:
                    topics = list(self._subscribers.keys())
                if not topics:
                    threading.Event().wait(0.1)
                    continue

                streams = {self._stream_key(t): ">" for t in topics}
                try:
                    entries = self.client.xreadgroup(
                        self.group_name, consumer_name, streams, count=10, block=500
                    )
                    if not entries:
                        continue
                    for stream_name, messages in entries:
                        s_name = stream_name.decode() if isinstance(stream_name, bytes) else stream_name
                        topic = s_name.replace(self.stream_prefix, "", 1)
                        for msg_id, fields in messages:
                            raw_payload = fields.get(b"payload") or fields.get("payload")
                            if isinstance(raw_payload, bytes):
                                raw_payload = raw_payload.decode()
                            payload = json.loads(raw_payload) if raw_payload else {}

                            with self._lock:
                                handlers = list(self._subscribers.get(topic, []))
                            for h in handlers:
                                try:
                                    h(payload)
                                except Exception as exc:
                                    logger.error(f"Error handling event {msg_id} on {topic}: {exc}")

                            self.client.xack(s_name, self.group_name, msg_id)
                except Exception as exc:
                    if self._running:
                        logger.warning(f"Error reading from Redis Streams: {exc}")
                        threading.Event().wait(1.0)

        self._consumer_thread = threading.Thread(target=_consume_loop, daemon=True)
        self._consumer_thread.start()

    def stop_consumer(self) -> None:
        self._running = False
        if self._consumer_thread and self._consumer_thread.is_alive():
            self._consumer_thread.join(timeout=1.0)
