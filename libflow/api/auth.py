"""
JWT Authentication & Role-Based Access Control (RBAC) Middleware.

Tokens are signed using HMAC-SHA256 (HS256). The signing secret comes from
``LIBRAFLOW_SECRET_KEY`` (see ``libflow.config``). Unauthenticated requests
to protected routes receive a clear 401 response — there is no silent
anonymous fallback.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import jwt
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from libflow.config import get_secret_key
from libflow.core.enums import UserRole
from libflow.core.user import User

_ALGORITHM = "HS256"
_DEFAULT_EXPIRY = 3600  # 1 hour

security_bearer = HTTPBearer(auto_error=False)


def create_access_token(
    user: User,
    expires_delta_seconds: int = _DEFAULT_EXPIRY,
) -> str:
    """Create an HS256-signed JWT carrying identity, role and permissions."""
    payload: Dict[str, Any] = {
        "sub": user.user_id,
        "name": user.name,
        "role": user.get_role().value,
        "permissions": list(user.get_permissions()),
        "iat": int(time.time()),
        "exp": int(time.time()) + expires_delta_seconds,
    }
    return jwt.encode(payload, get_secret_key(), algorithm=_ALGORITHM)


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode and verify a JWT. Raises HTTPException on any failure."""
    try:
        return jwt.decode(token, get_secret_key(), algorithms=[_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user_claims(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_bearer),
) -> Dict[str, Any]:
    """
    Dependency that returns the decoded token claims.

    If no bearer token is supplied the request is rejected with 401. Routes
    that should be public use a separate, explicit handler.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Please provide a Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return decode_access_token(credentials.credentials)


def require_role(allowed_roles: List[str]):
    """Dependency factory: ensures the caller has one of *allowed_roles*."""

    def _role_checker(
        claims: Dict[str, Any] = Depends(get_current_user_claims),
    ) -> Dict[str, Any]:
        user_role = claims.get("role", "")
        if user_role not in allowed_roles and user_role != UserRole.ADMIN.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Operation not permitted for role '{user_role}'. "
                    f"Requires one of {allowed_roles}."
                ),
            )
        return claims

    return _role_checker


def require_permission(permission: str):
    """Dependency factory: ensures the caller holds *permission* (or ALL)."""

    def _perm_checker(
        claims: Dict[str, Any] = Depends(get_current_user_claims),
    ) -> Dict[str, Any]:
        permissions = claims.get("permissions", [])
        if permission not in permissions and "ALL" not in permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permission: '{permission}'.",
            )
        return claims

    return _perm_checker
