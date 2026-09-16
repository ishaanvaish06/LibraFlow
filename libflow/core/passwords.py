"""
Password hashing utilities.

Uses passlib with bcrypt by default.  Call ``hash_password`` when accepting
new credentials and ``verify_password`` during login.
"""

from __future__ import annotations

from passlib.context import CryptContext

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    """Return a bcrypt hash of *plain* with a freshly generated salt.

    Guarantees every hashed password has a unique cryptographic salt,
    protecting against rainbow tables and identical-password correlation.
    """
    return _pwd_ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if *plain* matches the stored *hashed* value."""
    if not hashed:
        return False
    return _pwd_ctx.verify(plain, hashed)
