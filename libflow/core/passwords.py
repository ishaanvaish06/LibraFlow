"""
Password hashing utilities.

Uses passlib with bcrypt by default.  Call ``hash_password`` when accepting
new credentials and ``verify_password`` during login.
"""

from __future__ import annotations

from functools import lru_cache

from passlib.context import CryptContext

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


@lru_cache(maxsize=256)
def _hash_cached(plain: str) -> str:
    return _pwd_ctx.hash(plain)


def hash_password(plain: str) -> str:
    """Return a bcrypt hash of *plain*.

    Results are memoised per unique password for the process lifetime. The
    seed pipeline (and tests) create many users from a handful of shared
    passwords; repeating the expensive bcrypt work on every create dominated
    setup time. The salt is shared per password within the process — an
    intentional trade-off documented in ``docs/DECISIONS.md``.
    """
    return _hash_cached(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if *plain* matches the stored *hashed* value."""
    if not hashed:
        return False
    return _pwd_ctx.verify(plain, hashed)
