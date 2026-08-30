"""
Unit Tests for Phase 5: Persistence, Concurrency & Distributed Caching
"""
import pytest
import threading
import time
from libflow.storage.lock_manager import ConcurrencyLockManager
from libflow.storage.cache import DistributedCache
from libflow.storage.database import LibraryDatabase
from libflow.core.book import PhysicalBook, BookCopy
from libflow.core.user import Student


def test_concurrency_lock_manager_pessimistic():
    lock_mgr = ConcurrencyLockManager()
    counter = 0

    def worker():
        nonlocal counter
        for _ in range(100):
            with lock_mgr.acquire_pessimistic_lock("RESOURCE_1"):
                temp = counter
                time.sleep(0.0001)
                counter = temp + 1

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Must be precisely 500 without race condition corruption
    assert counter == 500


def test_concurrency_lock_manager_optimistic():
    lock_mgr = ConcurrencyLockManager()
    v1 = lock_mgr.get_version("DOC-1")
    assert v1 == 1

    v2 = lock_mgr.check_and_update_version("DOC-1", expected_version=1)
    assert v2 == 2

    # Expecting outdated version should fail
    with pytest.raises(ValueError, match="Optimistic lock conflict"):
        lock_mgr.check_and_update_version("DOC-1", expected_version=1)


def test_distributed_cache_lru_and_cache_aside():
    cache = DistributedCache(capacity=2)

    # Set items
    cache.set("k1", "val1")
    cache.set("k2", "val2")

    # Access k1 to make it MRU
    assert cache.get("k1") == "val1"

    # Insert k3 (should evict k2 since k1 was recently accessed)
    cache.set("k3", "val3")
    assert cache.get("k1") == "val1"
    assert cache.get("k3") == "val3"
    assert cache.get("k2") is None  # Evicted

    # Cache-Aside pattern
    fetch_count = 0

    def db_loader():
        nonlocal fetch_count
        fetch_count += 1
        return "expensive_db_result"

    # 1st call -> loader called
    val1 = cache.get_or_compute("k_expensive", db_loader)
    assert val1 == "expensive_db_result"
    assert fetch_count == 1

    # 2nd call -> served from cache without calling loader
    val2 = cache.get_or_compute("k_expensive", db_loader)
    assert val2 == "expensive_db_result"
    assert fetch_count == 1  # Still 1!


def test_database_acid_transaction_rollback():
    db = LibraryDatabase()
    book = PhysicalBook(isbn="ISBN-99", title="ACID DB", authors=["Author"], category="DB", publication_year=2024)
    db.save_book(book)

    assert db.get_book("ISBN-99") is not None

    # Failed transaction rolls back changes
    with pytest.raises(RuntimeError):
        with db.transaction():
            db.books.pop("ISBN-99")
            db.save_book(PhysicalBook(isbn="ISBN-FAIL", title="Fail", authors=[], category="", publication_year=2024))
            raise RuntimeError("Simulated crash mid-transaction")

    # State restored
    assert db.get_book("ISBN-99") is not None
    assert db.get_book("ISBN-FAIL") is None
