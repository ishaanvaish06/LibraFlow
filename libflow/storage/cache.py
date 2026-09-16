"""
Cache abstraction.

``Cache`` is the contract services rely on. Two implementations exist:

* ``InMemoryCache`` — LRU eviction, thread-safe; used in unit tests and as
  the offline-dev fallback.
* ``RedisCache`` (``libflow.storage.redis_cache``) — real distributed cache
  used in deployed environments.

Both implement cache-aside via ``get_or_compute``.
"""

from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod
from collections import OrderedDict
from typing import Any, Callable, Dict, Optional


class Cache(ABC):
    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """Return the cached value for *key*, or None on miss/expiry."""

    @abstractmethod
    def set(self, key: str, value: Any, ttl_seconds: Optional[float] = 300.0) -> None:
        ...

    @abstractmethod
    def invalidate(self, key: str) -> bool:
        ...

    @abstractmethod
    def invalidate_prefix(self, prefix: str) -> int:
        ...

    @abstractmethod
    def get_or_compute(
        self,
        key: str,
        compute_fn: Callable[[], Any],
        ttl_seconds: float = 300.0,
    ) -> Any:
        ...

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        ...


class CacheEntry:
    def __init__(self, key: str, value: Any, ttl_seconds: Optional[float] = None):
        self.key = key
        self.value = value
        self.expires_at = time.time() + ttl_seconds if ttl_seconds else None

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at


class InMemoryCache(Cache):
    """
    Thread-safe LRU cache implementing the ``Cache`` contract.

    Capacity-limited; least-recently-used entries are evicted on insert.
    """

    def __init__(self, capacity: int = 1000):
        self.capacity = capacity
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._cache.get(key)
            if entry is None or entry.is_expired():
                self._cache.pop(key, None)
                self.misses += 1
                return None
            self._cache.move_to_end(key)
            self.hits += 1
            return entry.value

    def set(self, key: str, value: Any, ttl_seconds: Optional[float] = 300.0) -> None:
        with self._lock:
            if key in self._cache:
                del self._cache[key]
            elif len(self._cache) >= self.capacity:
                self._cache.popitem(last=False)
            self._cache[key] = CacheEntry(key, value, ttl_seconds)

    def invalidate(self, key: str) -> bool:
        with self._lock:
            return self._cache.pop(key, None) is not None

    def invalidate_prefix(self, prefix: str) -> int:
        with self._lock:
            keys = [k for k in self._cache if k.startswith(prefix)]
            for k in keys:
                del self._cache[k]
            return len(keys)

    def get_or_compute(
        self,
        key: str,
        compute_fn: Callable[[], Any],
        ttl_seconds: float = 300.0,
    ) -> Any:
        cached = self.get(key)
        if cached is not None:
            return cached
        computed = compute_fn()
        if computed is not None:
            self.set(key, computed, ttl_seconds=ttl_seconds)
        return computed

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            total = self.hits + self.misses
            hit_ratio = (self.hits / total) if total > 0 else 0.0
            return {
                "backend": "in_memory",
                "size": len(self._cache),
                "capacity": self.capacity,
                "hits": self.hits,
                "misses": self.misses,
                "hit_ratio_pct": round(hit_ratio * 100, 2),
            }
