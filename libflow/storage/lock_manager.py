"""
Concurrency Lock Manager: Pessimistic & Optimistic Locking
Guarantees zero double-checkout anomalies under high concurrent requests.
"""
from typing import Dict, Optional, Any
import threading
import time
from contextlib import contextmanager


class ConcurrencyLockManager:
    """
    Manages resource-level mutexes (pessimistic locking) and version counters (optimistic locking).
    """

    def __init__(self):
        self._mutexes: Dict[str, threading.Lock] = {}
        self._master_lock = threading.Lock()
        # resource_id -> version_number
        self._versions: Dict[str, int] = {}

    def _get_resource_mutex(self, resource_id: str) -> threading.Lock:
        with self._master_lock:
            if resource_id not in self._mutexes:
                self._mutexes[resource_id] = threading.Lock()
            return self._mutexes[resource_id]

    @contextmanager
    def acquire_pessimistic_lock(self, resource_id: str, timeout: float = 5.0):
        """
        Pessimistic Lock: Exclusive lock on a single copy ID or user ID.
        """
        mutex = self._get_resource_mutex(resource_id)
        acquired = mutex.acquire(timeout=timeout)
        if not acquired:
            raise TimeoutError(f"Could not acquire lock for resource '{resource_id}' within {timeout}s.")
        try:
            yield
        finally:
            mutex.release()

    def get_version(self, resource_id: str) -> int:
        with self._master_lock:
            return self._versions.get(resource_id, 1)

    def check_and_update_version(self, resource_id: str, expected_version: int) -> int:
        """
        Optimistic Locking: Checks if version matches, then increments.
        Raises ValueError if concurrent modification detected.
        """
        with self._master_lock:
            current_version = self._versions.get(resource_id, 1)
            if current_version != expected_version:
                raise ValueError(
                    f"Optimistic lock conflict on '{resource_id}': expected v{expected_version}, but was v{current_version}."
                )
            new_version = current_version + 1
            self._versions[resource_id] = new_version
            return new_version
