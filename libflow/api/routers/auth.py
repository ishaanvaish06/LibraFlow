"""Authentication routes."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends

from libflow.api.auth import create_access_token, get_current_user_claims
from libflow.api.dependencies import get_user_repository
from libflow.api.schemas import TokenResponse, UserLoginRequest, UserRegisterRequest
from libflow.core.exceptions import DuplicateUserError, UserNotFoundError
from libflow.core.factory import UserFactory
from libflow.core.passwords import verify_password
from libflow.storage.repository import UserRepository

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


@router.post("/register")
def register_user(
    req: UserRegisterRequest,
    user_repo: UserRepository = Depends(get_user_repository),
) -> Dict[str, Any]:
    if user_repo.user_exists(req.user_id):
        raise DuplicateUserError(req.user_id)
    user = UserFactory.create_user(
        role=req.role,
        user_id=req.user_id,
        name=req.name,
        email=req.email,
        password=req.password,
        academic_year=req.academic_year or 1,
        major=req.major or "Computer Science",
        branch_id=req.branch_id or "BRANCH-DELHI",
    )
    user_repo.save_user(user)
    return {"status": "SUCCESS", "user": user.to_dict()}


@router.post("/login", response_model=TokenResponse)
def login_user(
    req: UserLoginRequest,
    user_repo: UserRepository = Depends(get_user_repository),
) -> TokenResponse:
    user = user_repo.get_user(req.user_id)
    if not user:
        raise UserNotFoundError(req.user_id)
    if not verify_password(req.password, user.password_hash):
        from fastapi import HTTPException

        raise HTTPException(status_code=401, detail="Invalid credentials.")
    token = create_access_token(user)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user_id=user.user_id,
        role=user.get_role().value,
        name=user.name,
    )


@router.get("/me")
def get_current_profile(
    claims: Dict[str, Any] = Depends(get_current_user_claims),
    user_repo: UserRepository = Depends(get_user_repository),
) -> Dict[str, Any]:
    user = user_repo.get_user(claims.get("sub", ""))
    if not user:
        return claims
    return user.to_dict()