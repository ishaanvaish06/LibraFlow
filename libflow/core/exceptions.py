"""
Domain exceptions for LibraFlow.

Services and core models raise these types; the FastAPI layer translates
each one to an HTTP response in exactly one place (``libflow/api/app.py``).
HTTPException must never leak into service/model code.
"""

from __future__ import annotations

from typing import Any, Optional


class DomainError(Exception):
    """Base class for all expected domain errors."""


class NotFoundError(DomainError):
    """Base class for 'resource does not exist' errors."""

    def __init__(self, resource_type: str, resource_id: str):
        self.resource_type = resource_type
        self.resource_id = resource_id
        super().__init__(f"{resource_type} '{resource_id}' not found.")


class BookNotFoundError(NotFoundError):
    def __init__(self, isbn: str):
        super().__init__("Book", isbn)


class UserNotFoundError(NotFoundError):
    def __init__(self, user_id: str):
        super().__init__("User", user_id)


class CopyNotFoundError(NotFoundError):
    def __init__(self, copy_id: str):
        super().__init__("Book copy", copy_id)


class BranchNotFoundError(NotFoundError):
    def __init__(self, branch_id: str):
        super().__init__("Branch", branch_id)


class DuplicateResourceError(DomainError):
    def __init__(self, resource_type: str, resource_id: str):
        self.resource_type = resource_type
        self.resource_id = resource_id
        super().__init__(f"{resource_type} '{resource_id}' already exists.")


class DuplicateUserError(DuplicateResourceError):
    def __init__(self, user_id: str):
        super().__init__("User", user_id)


class InvalidStateTransitionError(DomainError):
    """Raised when a state machine transition is not allowed."""

    def __init__(self, message: str, state: Optional[str] = None):
        self.state = state
        super().__init__(message)


class CopyUnavailableError(DomainError):
    def __init__(self, copy_id: str, status: Optional[str] = None):
        self.copy_id = copy_id
        self.status = status
        detail = f"Copy '{copy_id}' is not available."
        if status:
            detail += f" Current status: {status}."
        super().__init__(detail)


class UserNotEligibleError(DomainError):
    def __init__(self, user_id: str, reason: str):
        self.user_id = user_id
        self.reason = reason
        super().__init__(f"User '{user_id}' is not eligible to borrow: {reason}.")


class OptimisticLockConflictError(DomainError):
    def __init__(self, resource_id: str, expected: int, actual: int):
        self.resource_id = resource_id
        self.expected_version = expected
        self.actual_version = actual
        super().__init__(
            f"Optimistic lock conflict on '{resource_id}': "
            f"expected version {expected}, found {actual}."
        )


class PermissionDeniedError(DomainError):
    def __init__(self, permission: str, role: Optional[str] = None):
        self.permission = permission
        self.role = role
        detail = f"Missing required permission: '{permission}'."
        if role:
            detail += f" Caller role: {role}."
        super().__init__(detail)


class InsufficientInputError(DomainError):
    """Raised for invalid arguments to domain operations."""

    def __init__(self, detail: str, cause: Optional[Any] = None):
        self.detail = detail
        super().__init__(detail)


class TransferError(DomainError):
    def __init__(self, message: str, transfer_id: Optional[str] = None):
        self.transfer_id = transfer_id
        super().__init__(message)
