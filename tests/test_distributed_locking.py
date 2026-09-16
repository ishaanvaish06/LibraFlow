"""
Tests for ConcurrencyLockManager:
- In-memory pessimistic locking and timeouts
- In-memory optimistic locking and conflicts
- Distributed Redis pessimistic locking (SET NX PX + Lua atomic unlock)
- Distributed Redis optimistic locking (atomic Lua check-and-update)
"""

from __future__ import annotations

import threading
import time
import pytest
from unittest.mock import MagicMock

from libflow.storage.lock_manager import ConcurrencyLockManager, LUA_RELEASE_LOCK, LUA_OPTIMISTIC_VERSION


def test_in_memory_pessimistic_lock():
    lock_mgr = ConcurrencyLockManager()
    counter = 0

    def worker():
        nonlocal counter
        for _ in range(50):
            with lock_mgr.acquire_pessimistic_lock("RES-A", timeout=5.0):
                val = counter
                time.sleep(0.0001)
                counter = val + 1

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert counter == 200


def test_in_memory_lock_timeout():
    lock_mgr = ConcurrencyLockManager()
    acquired_event = threading.Event()
    release_event = threading.Event()

    def holding_worker():
        with lock_mgr.acquire_pessimistic_lock("BLOCKED-RES", timeout=2.0):
            acquired_event.set()
            release_event.wait(timeout=3.0)

    t = threading.Thread(target=holding_worker)
    t.start()

    acquired_event.wait(timeout=1.0)
    # Trying to acquire the same resource with a short timeout must raise TimeoutError
    with pytest.raises(TimeoutError, match="Could not acquire lock"):
        with lock_mgr.acquire_pessimistic_lock("BLOCKED-RES", timeout=0.1):
            pass

    release_event.set()
    t.join()


def test_in_memory_optimistic_locking():
    lock_mgr = ConcurrencyLockManager()
    assert lock_mgr.get_version("ITEM-1") == 1

    v2 = lock_mgr.check_and_update_version("ITEM-1", expected_version=1)
    assert v2 == 2
    assert lock_mgr.get_version("ITEM-1") == 2

    with pytest.raises(ValueError, match="Optimistic lock conflict"):
        lock_mgr.check_and_update_version("ITEM-1", expected_version=1)


class MockRedis:
    """In-memory Redis emulator supporting SET NX PX and EVAL for lock script testing."""

    def __init__(self):
        self.store = {}
        self.lock = threading.Lock()

    def set(self, key, value, nx=False, px=None):
        with self.lock:
            if nx and key in self.store:
                return False
            self.store[key] = value
            return True

    def get(self, key):
        with self.lock:
            val = self.store.get(key)
            return val if val is None else str(val)

    def delete(self, *keys):
        with self.lock:
            count = 0
            for k in keys:
                if k in self.store:
                    del self.store[k]
                    count += 1
            return count

    def eval(self, script, numkeys, *args):
        with self.lock:
            if script == LUA_RELEASE_LOCK:
                key, token = args[0], args[1]
                if self.store.get(key) == token:
                    del self.store[key]
                    return 1
                return 0
            elif script == LUA_OPTIMISTIC_VERSION:
                key, expected = args[0], int(args[1])
                current = int(self.store.get(key, 1))
                if current == expected:
                    new_val = current + 1
                    self.store[key] = str(new_val)
                    return new_val
                return -1
            raise NotImplementedError("Script not handled in mock")


def test_distributed_redis_locking_flow():
    mock_redis = MockRedis()
    lock_mgr = ConcurrencyLockManager(redis_client=mock_redis)

    # Acquire lock on copy
    with lock_mgr.acquire_pessimistic_lock("COPY-001", timeout=1.0) as token:
        assert token is not None
        assert mock_redis.get("lock:COPY-001") == token

        # Concurrently attempting to acquire from another thread should timeout
        other_acquired = False
        def try_other():
            nonlocal other_acquired
            try:
                with lock_mgr.acquire_pessimistic_lock("COPY-001", timeout=0.1, retry_interval=0.01):
                    other_acquired = True
            except TimeoutError:
                other_acquired = False

        t = threading.Thread(target=try_other)
        t.start()
        t.join()
        assert not other_acquired

    # After exiting block, lock should be released
    assert mock_redis.get("lock:COPY-001") is None


def test_distributed_redis_optimistic_locking():
    mock_redis = MockRedis()
    lock_mgr = ConcurrencyLockManager(redis_client=mock_redis)

    assert lock_mgr.get_version("RESOURCE-X") == 1
    v2 = lock_mgr.check_and_update_version("RESOURCE-X", expected_version=1)
    assert v2 == 2

    # Wrong version raises conflict
    with pytest.raises(ValueError, match="Optimistic lock conflict"):
        lock_mgr.check_and_update_version("RESOURCE-X", expected_version=1)

    v3 = lock_mgr.check_and_update_version("RESOURCE-X", expected_version=2)
    assert v3 == 3
