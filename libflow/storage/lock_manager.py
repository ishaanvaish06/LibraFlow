"""
Concurrency Lock Manager: Pessimistic & Optimistic Locking
Guarantees zero double-checkout anomalies under high concurrent requests.
Supports in-memory locks for single-node / testing, and Redis-backed distributed locks
(SET NX PX + Lua script unlock) across multi-process / multi-replica deployments.
"""
from typing import Dict, Optional, Any
import threading
import time
import uuid
from contextlib import contextmanager

LUA_RELEASE_LOCK = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""

LUA_OPTIMISTIC_VERSION = """
local current = redis.call("get", KEYS[1])
if not current then
    current = "1"
end
if tonumber(current) == tonumber(ARGV[1]) then
    local next_val = tonumber(current) + 1
    redis.call("set", KEYS[1], tostring(next_val))
    return next_val
else
    return -1
end
"""


class ConcurrencyLockManager:
    """
    Manages resource-level mutexes (pessimistic locking) and version counters (optimistic locking).
    Can operate in in-memory mode or distributed Redis mode.
    """

    def __init__(self, redis_client: Optional[Any] = None, key_prefix: str = "lock:"):
        self.redis_client = redis_client
        self.key_prefix = key_prefix
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
    def acquire_pessimistic_lock(
        self,
        resource_id: str,
        timeout: float = 5.0,
        expire_seconds: float = 10.0,
        retry_interval: float = 0.02,
    ):
        """
        Pessimistic Lock: Exclusive lock on a single copy ID or user ID.
        Uses Redis SET NX PX when Redis is configured; falls back to in-process mutex.
        """
        if self.redis_client is not None:
            lock_key = f"{self.key_prefix}{resource_id}"
            token = str(uuid.uuid4())
            expire_ms = int(expire_seconds * 1000)
            deadline = time.time() + timeout
            acquired = False

            while time.time() < deadline:
                res = self.redis_client.set(lock_key, token, nx=True, px=expire_ms)
                if res:
                    acquired = True
                    break
                time.sleep(retry_interval)

            if not acquired:
                raise TimeoutError(f"Could not acquire distributed lock for resource '{resource_id}' within {timeout}s.")

            try:
                yield token
            finally:
                try:
                    self.redis_client.eval(LUA_RELEASE_LOCK, 1, lock_key, token)
                except Exception:
                    pass
        else:
            mutex = self._get_resource_mutex(resource_id)
            acquired = mutex.acquire(timeout=timeout)
            if not acquired:
                raise TimeoutError(f"Could not acquire lock for resource '{resource_id}' within {timeout}s.")
            try:
                yield
            finally:
                mutex.release()

    def get_version(self, resource_id: str) -> int:
        if self.redis_client is not None:
            val = self.redis_client.get(f"ver:{resource_id}")
            if val is not None:
                try:
                    return int(val)
                except (ValueError, TypeError):
                    pass
            return 1
        with self._master_lock:
            return self._versions.get(resource_id, 1)

    def check_and_update_version(self, resource_id: str, expected_version: int) -> int:
        """
        Optimistic Locking: Checks if version matches, then increments.
        Raises ValueError if concurrent modification detected.
        """
        if self.redis_client is not None:
            ver_key = f"ver:{resource_id}"
            res = self.redis_client.eval(LUA_OPTIMISTIC_VERSION, 1, ver_key, expected_version)
            if res == -1:
                current_val = self.get_version(resource_id)
                raise ValueError(
                    f"Optimistic lock conflict on '{resource_id}': expected v{expected_version}, but was v{current_val}."
                )
            return int(res)

        with self._master_lock:
            current_version = self._versions.get(resource_id, 1)
            if current_version != expected_version:
                raise ValueError(
                    f"Optimistic lock conflict on '{resource_id}': expected v{expected_version}, but was v{current_version}."
                )
            new_version = current_version + 1
            self._versions[resource_id] = new_version
            return new_version
