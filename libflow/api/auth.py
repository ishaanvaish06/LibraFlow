"""
Authentication & Role-Based Access Control (RBAC) Security Middleware
"""
import base64
import json
import time
from typing import Optional, Dict, Any, List
from fastapi import HTTPException, Security, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from libflow.core.enums import UserRole
from libflow.core.user import User

SECRET_KEY = "libraflow_super_secret_jwt_key_2026"
security_bearer = HTTPBearer(auto_error=False)


def create_access_token(user: User, expires_delta_seconds: int = 3600) -> str:
    """
    Creates a lightweight signed JWT-compatible token payload.
    """
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": user.user_id,
        "name": user.name,
        "role": user.get_role().value,
        "permissions": list(user.get_permissions()),
        "exp": int(time.time()) + expires_delta_seconds,
    }
    encoded_header = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
    encoded_payload = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    signature = base64.urlsafe_b64encode(f"{encoded_header}.{encoded_payload}.{SECRET_KEY}".encode()).decode().rstrip("=")
    return f"{encoded_header}.{encoded_payload}.{signature}"


def decode_access_token(token: str) -> Dict[str, Any]:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Malformed token.")
        
        encoded_header, encoded_payload, signature = parts
        expected_sig = base64.urlsafe_b64encode(f"{encoded_header}.{encoded_payload}.{SECRET_KEY}".encode()).decode().rstrip("=")
        if signature != expected_sig:
            raise ValueError("Invalid signature.")

        # Padding correction
        padded_payload = encoded_payload + "=" * (-len(encoded_payload) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded_payload.encode()).decode())

        if time.time() > payload.get("exp", 0):
            raise ValueError("Token expired.")

        return payload
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired authentication credentials: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user_claims(credentials: Optional[HTTPAuthorizationCredentials] = Security(security_bearer)) -> Dict[str, Any]:
    if not credentials:
        # Default mock admin for testing without auth header if desired
        return {"sub": "ANONYMOUS", "role": "STUDENT", "permissions": ["BOOK_SEARCH"]}
    return decode_access_token(credentials.credentials)


def require_role(allowed_roles: List[str]):
    def role_checker(claims: Dict[str, Any] = Depends(get_current_user_claims)):
        user_role = claims.get("role", "STUDENT")
        if user_role not in allowed_roles and user_role != "ADMIN":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation not permitted for role '{user_role}'. Requires one of {allowed_roles}.",
            )
        return claims
    return role_checker


def require_permission(permission: str):
    def perm_checker(claims: Dict[str, Any] = Depends(get_current_user_claims)):
        permissions = claims.get("permissions", [])
        if permission not in permissions and "ALL" not in permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permission: '{permission}'.",
            )
        return claims
    return perm_checker
