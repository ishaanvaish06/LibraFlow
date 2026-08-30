"""
Distributed Cache System (Redis-Compatible Simulation)
Implements LRU Eviction, Cache-Aside Pattern, TTL, and Invalidation Policies.
"""
from typing import Dict, Any, Optional, Tuple, Callable
from collections import OrderedDict
import time
import threading


class CacheEntry:
    def __init__(self, key: str, value: Any, ttl_seconds: Optional[float] = None):
        self.key = key
        self.value = value
        self.expires_at = time.time() + ttl_seconds if ttl_seconds else None

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at


class DistributedCache:
    """
    Thread-safe in-memory cache simulating a Redis cluster with LRU eviction and Cache-Aside helper.
    """

    def __init__(self, capacity: int = 1000):
        self.capacity = capacity
        # key -> CacheEntry (OrderedDict for LRU)
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key not in self._cache:
                self.misses += 1
                return None

            entry = self._cache[key]
            if entry.is_expired():
                del self._cache[key]
                self.misses += 1
                return None

            # Move to MRU position
            self._cache.move_to_end(key)
            self.hits += 1
            return entry.value

    def set(self, key: str, value: Any, ttl_seconds: Optional[float] = 300.0) -> None:
        with self._lock:
            if key in self._cache:
                del self._cache[key]
            elif len(self._cache) >= self.capacity:
                # Evict oldest LRU entry
                self._cache.popitem(last=False)

            self._cache[key] = CacheEntry(key, value, ttl_seconds)

    def invalidate(self, key: str) -> bool:
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def invalidate_prefix(self, prefix: str) -> int:
        with self._lock:
            keys_to_del = [k for k in self._cache.keys() if k.startswith(prefix)]
            for k in keys_to_del:
                del self._cache[k]
            return len(keys_to_del)

    def get_or_compute(self, key: str, compute_fn: Callable[[], Any], ttl_seconds: float = 300.0) -> Any:
        """
        Implements the Cache-Aside pattern: returns cached value or executes loader function and caches result.
        """
        cached = self.get(key)
        if cached is not None:
            return cached

        # Cache miss: compute from database / source
        computed = compute_fn()
        if computed is not None:
            self.set(key, computed, ttl_seconds=ttl_seconds)
        return computed

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            total_requests = self.hits + self.misses
            hit_ratio = (self.hits / total_requests) if total_requests > 0 else 0.0
            return {
                "size": len(self._cache),
                "capacity": self.capacity,
                "hits": self.hits,
                "misses": self.misses,
                "hit_ratio_pct": round(hit_ratio * 100, 2),
            }
