"""
Redis-backed cache implementing the ``Cache`` contract.

Values are serialised to JSON/msgpack for transport. ``get_or_compute``
implements the cache-aside pattern (read-through with populate on miss).

Connection failures degrade to a no-op (miss) so reads still hit the source
of truth when Redis is unavailable; this is a deliberate trade-off documented
in ``docs/DECISIONS.md``.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Dict, Optional

import redis

from libflow.storage.cache import Cache

logger = logging.getLogger(__name__)


def _serialize(value: Any) -> str:
    return json.dumps(value, default=str, ensure_ascii=False)


def _deserialize(raw: Optional[bytes]) -> Optional[Any]:
    if raw is None:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return raw.decode("utf-8")


class RedisCache(Cache):
    def __init__(self, client: redis.Redis):
        self._client = client
        self.hits = 0
        self.misses = 0

    def _connection_ok(self) -> bool:
        try:
            return self._client.ping()
        except redis.RedisError:
            logger.warning("Redis unavailable; caching disabled for this operation.")
            return False

    def get(self, key: str) -> Optional[Any]:
        try:
            value = self._client.get(key)
            if value is None:
                self.misses += 1
                return None
            self.hits += 1
            return _deserialize(value)
        except redis.RedisError:
            self.misses += 1
            return None

    def set(self, key: str, value: Any, ttl_seconds: Optional[float] = 300.0) -> None:
        try:
            payload = _serialize(value)
            if ttl_seconds is None:
                self._client.set(key, payload)
            else:
                self._client.setex(key, int(ttl_seconds), payload)
        except redis.RedisError:
            logger.warning("Redis unavailable; skipping set for key '%s'.", key)

    def invalidate(self, key: str) -> bool:
        try:
            return bool(self._client.delete(key))
        except redis.RedisError:
            return False

    def invalidate_prefix(self, prefix: str) -> int:
        try:
            keys = [k for k in self._client.scan_iter(f"{prefix}*")]
            if not keys:
                return 0
            return int(self._client.delete(*keys))
        except redis.RedisError:
            return 0

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
        try:
            info = self._client.info("stats")
            connected_clients = self._client.info("clients").get("connected_clients", 0)
        except redis.RedisError:
            info, connected_clients = {}, 0
        total = self.hits + self.misses
        hit_ratio = (self.hits / total) if total > 0 else 0.0
        return {
            "backend": "redis",
            "hits": self.hits,
            "misses": self.misses,
            "hit_ratio_pct": round(hit_ratio * 100, 2),
            "redis_keyspace_hits": info.get("keyspace_hits", 0),
            "redis_keyspace_misses": info.get("keyspace_misses", 0),
            "connected_clients": connected_clients,
        }

    @classmethod
    def from_settings(cls, host: str, port: int, db: int = 0, password: Optional[str] = None) -> "RedisCache":
        client = redis.Redis(host=host, port=port, db=db, password=password, decode_responses=False)
        return cls(client)