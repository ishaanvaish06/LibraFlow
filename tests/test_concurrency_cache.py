"""
Unit tests for locking, the LRU cache, and exactly-once checkout under
concurrency.
"""

from __future__ import annotations

import threading

import pytest

from libflow.core.enums import BookStatus
from libflow.services.circulation_service import CirculationService
from libflow.storage.cache import InMemoryCache
from libflow.storage.lock_manager import ConcurrencyLockManager

BARRIER_COUNT = 8


def test_concurrency_lock_manager_pessimistic():
    lock_mgr = ConcurrencyLockManager()
    counter = 0

    def worker():
        nonlocal counter
        for _ in range(100):
            with lock_mgr.acquire_pessimistic_lock("RESOURCE_1"):
                temp = counter
                counter = temp + 1

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert counter == 500


def test_concurrency_lock_manager_optimistic():
    lock_mgr = ConcurrencyLockManager()
    assert lock_mgr.get_version("DOC-1") == 1

    v2 = lock_mgr.check_and_update_version("DOC-1", expected_version=1)
    assert v2 == 2

    with pytest.raises(ValueError, match="Optimistic lock conflict"):
        lock_mgr.check_and_update_version("DOC-1", expected_version=1)


def test_in_memory_cache_lru_and_cache_aside():
    cache = InMemoryCache(capacity=2)

    cache.set("k1", "val1")
    cache.set("k2", "val2")
    assert cache.get("k1") == "val1"  # moves k1 to MRU end

    cache.set("k3", "val3")  # evicts k2 (LRU)
    assert cache.get("k3") == "val3"
    assert cache.get("k1") == "val1"
    assert cache.get("k2") is None

    fetch_count = 0

    def db_loader():
        nonlocal fetch_count
        fetch_count += 1
        return "expensive_db_result"

    assert cache.get_or_compute("k_expensive", db_loader) == "expensive_db_result"
    assert cache.get_or_compute("k_expensive", db_loader) == "expensive_db_result"
    assert fetch_count == 1

    stats = cache.get_stats()
    assert stats["hits"] >= 2
    assert stats["misses"] >= 1
    assert stats["hit_ratio_pct"] > 0


def test_in_memory_cache_invalidation():
    cache = InMemoryCache(capacity=100)
    cache.set("search:algorithms", [1, 2, 3])
    cache.set("search:databases", [4, 5])
    assert cache.invalidate_prefix("search:") == 2
    assert cache.get("search:algorithms") is None
    assert cache.invalidate("missing-key") is False


def test_exactly_one_concurrent_checkout_succeeds(container):
    """The storage-level per-copy lock guarantees a single winner."""
    from libflow.core.factory import UserFactory

    for i in range(BARRIER_COUNT):
        container.user_repo.save_user(
            UserFactory.create_user(
                role="STUDENT", user_id=f"STU-CONC-{i}", name=f"Conc{i}",
                email=f"conc{i}@test.com", password="passw0rd", academic_year=1,
            )
        )

    issue_svc: CirculationService = container.circulation_svc
    copy_id = "CC-DEL-02"
    barrier = threading.Barrier(BARRIER_COUNT)

    results: list[str] = []
    results_lock = threading.Lock()

    def try_issue(user_id: str, copy: str = copy_id):
        barrier.wait()
        try:
            issue_svc.issue_physical_book(copy, user_id, actor_id="ADMIN-01")
            outcome = "SUCCESS"
        except Exception as exc:
            outcome = type(exc).__name__
        with results_lock:
            results.append(outcome)

    threads = [
        threading.Thread(target=try_issue, args=(f"STU-CONC-{i}",)) for i in range(BARRIER_COUNT)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert results.count("SUCCESS") == 1
    copy_after = container.book_repo.get_copy(copy_id)
    assert copy_after.status in (BookStatus.ISSUED, BookStatus.RESERVED)


def test_issue_updates_user_history(container):
    svc: CirculationService = container.circulation_svc
    tx = svc.issue_physical_book("CC-DEL-02", "STU-ALICE", actor_id="ADMIN-01", loan_days=7)
    assert tx["type"] == "BORROW"
    alice = container.user_repo.get_user("STU-ALICE")
    assert "CC-DEL-02" in alice.active_borrowed_copy_ids