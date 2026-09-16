"""
Shared fixtures for the PostgreSQL/Redis integration suite.

These tests require a real database and are skipped unless
``TEST_DATABASE_URL`` (and optionally ``TEST_REDIS_HOST``) are present.
They are exercised by ``docker-compose.test.yml`` / CI; they do not run in
the default local invocation.
"""

from __future__ import annotations

import os

import pytest

from libflow.storage.postgres import DatabaseSessionFactory
from libflow.storage.redis_cache import RedisCache

pytestmark = pytest.mark.integration


def _env(name: str, default: str) -> str:
    return os.getenv(name, default)


@pytest.fixture
def session_factory() -> DatabaseSessionFactory:
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        user = os.getenv("DB_USER", "libraflow_user")
        pwd = os.getenv("DB_PASSWORD", "libraflow_secret")
        host = os.getenv("DB_HOST", "localhost")
        port = os.getenv("DB_PORT", "5432")
        db = os.getenv("DB_NAME", "libraflow_test")
        url = f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{db}"
    try:
        factory = DatabaseSessionFactory(url)
        factory.create_all()
    except Exception as exc:
        pytest.skip(f"PostgreSQL not reachable at {url}: {exc}")
    yield factory
    factory.dispose()


@pytest.fixture
def redis_cache() -> RedisCache:
    host = os.getenv("TEST_REDIS_HOST") or os.getenv("REDIS_HOST", "localhost")
    port = int(os.getenv("TEST_REDIS_PORT") or os.getenv("REDIS_PORT", "6379"))
    try:
        cache = RedisCache.from_settings(host=host, port=port)
        if not cache._client.ping():
            pytest.skip("Redis not reachable at %s:%s" % (host, port))
    except Exception as exc:
        pytest.skip(f"Redis not reachable at {host}:{port}: {exc}")
    cache._client.flushdb()
    yield cache
    try:
        cache._client.flushdb()
    except Exception:
        pass

