"""
Runtime configuration for LibraFlow.

Every value is read from the environment. Secrets fail fast in production:
the process refuses to start with a falsy/empty secret, instead of silently
falling back to an insecure default.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

ENVIRONMENT = os.getenv("ENVIRONMENT", "development").strip().lower()

_DEV_ONLY_SECRET = "libraflow-dev-only-secret-change-me"


def _fail_fast(message: str) -> None:
    raise RuntimeError(message)


def get_secret_key() -> str:
    """
    Returns LIBRAFLOW_SECRET_KEY.

    In production this is mandatory and the app must not boot without it.
    In development/testing a fixed key is used so docs & demos work out of
    the box. Never use the development key in a deployed environment.
    """
    key = os.getenv("LIBRAFLOW_SECRET_KEY", "").strip()
    if key:
        return key
    if ENVIRONMENT == "production":
        _fail_fast(
            "LIBRAFLOW_SECRET_KEY is not set. Refusing to start in production "
            "with an insecure default secret."
        )
    return _DEV_ONLY_SECRET


@dataclass(frozen=True)
class DatabaseSettings:
    host: str
    port: int
    name: str
    user: str
    password: str

    @property
    def url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.name}"
        )

    @classmethod
    def from_env(cls) -> "DatabaseSettings":
        return cls(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "5432")),
            name=os.getenv("DB_NAME", "libraflow"),
            user=os.getenv("DB_USER", "libraflow_user"),
            password=os.getenv("DB_PASSWORD", "libraflow_secret"),
        )


@dataclass(frozen=True)
class RedisSettings:
    host: str
    port: int
    db: int
    password: str | None

    @classmethod
    def from_env(cls) -> "RedisSettings":
        return cls(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            db=int(os.getenv("REDIS_DB", "0")),
            password=os.getenv("REDIS_PASSWORD") or None,
        )


def is_development() -> bool:
    return ENVIRONMENT in ("development", "dev", "test")
