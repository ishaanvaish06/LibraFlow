"""
Tests for Transactional Outbox pattern, OutboxRelay worker, and EventBus.
"""

from __future__ import annotations


from libflow.distributed.event_bus import InMemoryEventBus
from libflow.storage.outbox import InMemoryOutboxRepository, OutboxRelay
from libflow.api.dependencies import build_in_memory_container
from libflow.seed import seed_library


def test_in_memory_outbox_lifecycle():
    outbox = InMemoryOutboxRepository()
    bus = InMemoryEventBus()
    relay = OutboxRelay(outbox, bus, poll_interval=0.01)

    # 1. Save an event
    evt = outbox.save_event("book.borrowed", {"user_id": "U1", "isbn": "978-1"})
    assert evt["status"] == "PENDING"

    # 2. Check fetch_pending
    pending = outbox.fetch_pending(limit=10)
    assert len(pending) == 1
    assert pending[0]["event_id"] == evt["event_id"]

    # 3. Track events received on bus
    received = []
    bus.subscribe("book.borrowed", lambda p: received.append(p))

    # 4. Run relay once
    published = relay.publish_pending_once()
    assert published == 1
    assert len(received) == 1
    assert received[0]["user_id"] == "U1"

    # 5. Outbox status is now PUBLISHED
    assert len(outbox.fetch_pending(limit=10)) == 0
    assert outbox.events[0]["status"] == "PUBLISHED"
    assert outbox.events[0]["published_at"] is not None


def test_outbox_relay_error_retry():
    outbox = InMemoryOutboxRepository()
    bus = InMemoryEventBus()
    relay = OutboxRelay(outbox, bus, poll_interval=0.01)

    outbox.save_event("failing.topic", {"data": 123})

    def buggy_publish(topic, payload):
        raise ConnectionError("Broker connection dropped!")

    bus.publish = buggy_publish

    # Publishing will catch exception and mark event failed/retry
    published = relay.publish_pending_once()
    assert published == 0
    assert outbox.events[0]["retry_count"] == 1


def test_circulation_service_emits_outbox_events():
    container = build_in_memory_container()
    try:
        seed_library(container)
        outbox = InMemoryOutboxRepository()
        bus = InMemoryEventBus()
        relay = OutboxRelay(outbox, bus)

        # Wire outbox into circulation service
        container.circulation_svc.outbox_repo = outbox

        # Issue book
        tx = container.circulation_svc.issue_physical_book(
            copy_id="CC-DEL-02", user_id="STU-ALICE", actor_id="ADMIN-01"
        )
        assert tx is not None

        # Verify event in outbox
        pending = outbox.fetch_pending()
        assert len(pending) >= 1
        assert any(e["topic"] == "copy.issued" and e["payload"]["copy_id"] == "CC-DEL-02" for e in pending)

        # Return book
        ret = container.circulation_svc.return_physical_book(
            copy_id="CC-DEL-02", actor_id="ADMIN-01"
        )
        assert ret["status"] == "AVAILABLE"

        # Verify copy.returned event in outbox
        pending = outbox.fetch_pending()
        assert any(e["topic"] == "copy.returned" and e["payload"]["copy_id"] == "CC-DEL-02" for e in pending)

        # Publish all via relay
        published = relay.publish_pending_once()
        assert published >= 2
    finally:
        container.dispose()
