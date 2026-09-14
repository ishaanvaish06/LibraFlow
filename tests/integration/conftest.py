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
    url = _env(
        "TEST_DATABASE_URL",
        "postgresql+psycopg2://libraflow_user:libraflow_secret@localhost:5432/libraflow",
    )
    factory = DatabaseSessionFactory(url)
    factory.create_all()
    yield factory
    factory.dispose()


@pytest.fixture
def redis_cache() -> RedisCache:
    host = _env("TEST_REDIS_HOST", "localhost")
    port = int(_env("TEST_REDIS_PORT", "6379"))
    cache = RedisCache.from_settings(host=host, port=port)
    if not cache._client.ping():
        pytest.skip("Redis not reachable at %s:%s" % (host, port))
    cache._client.flushdb()
    yield cache
    cache._client.flushdb()