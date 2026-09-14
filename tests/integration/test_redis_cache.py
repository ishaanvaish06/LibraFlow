"""
Redis cache integration tests.

Exercised against a real Redis (see ``docker-compose.test.yml``). Skipped
locally when no Redis is reachable.
"""

from __future__ import annotations

import os
import time

import pytest

from libflow.storage.redis_cache import RedisCache

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.getenv("TEST_REDIS_HOST"),
        reason="TEST_REDIS_HOST not set (requires a running Redis)",
    ),
]


def test_set_get_round_trip(redis_cache: RedisCache) -> None:
    redis_cache.set("it:key", {"a": 1, "b": "x"})
    assert redis_cache.get("it:key") == {"a": 1, "b": "x"}


def test_ttl_expiry(redis_cache: RedisCache) -> None:
    redis_cache.set("it:short", 42, ttl_seconds=1)
    assert redis_cache.get("it:short") == 42
    time.sleep(1.2)
    assert redis_cache.get("it:short") is None


def test_invalidate(redis_cache: RedisCache) -> None:
    redis_cache.set("it:del", "v")
    assert redis_cache.invalidate("it:del") is True
    assert redis_cache.invalidate("it:del") is False


def test_invalidate_prefix(redis_cache: RedisCache) -> None:
    redis_cache.set("pfx:1", "a")
    redis_cache.set("pfx:2", "b")
    redis_cache.set("other:3", "c")
    assert redis_cache.invalidate_prefix("pfx:") == 2
    assert redis_cache.get("other:3") == "c"


def test_get_or_compute_populates_once(redis_cache: RedisCache) -> None:
    calls = {"n": 0}

    def compute() -> dict:
        calls["n"] += 1
        return {"n": calls["n"]}

    first = redis_cache.get_or_compute("it:compute", compute)
    second = redis_cache.get_or_compute("it:compute", compute)
    assert first == second == {"n": 1}
    assert calls["n"] == 1


def test_stats_are_reported(redis_cache: RedisCache) -> None:
    redis_cache.get("it:nope")
    redis_cache.set("it:stats", 7)
    redis_cache.get("it:stats")
    stats = redis_cache.get_stats()
    assert stats["backend"] == "redis"
    assert set(["hits", "misses", "hit_ratio_pct"]).issubset(stats)
    assert stats["misses"] >= 1
    assert stats["hits"] >= 1