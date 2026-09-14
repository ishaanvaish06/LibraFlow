"""
Unit tests for the domain exception vocabulary and its rendering.
"""

from __future__ import annotations

from libflow.core.exceptions import (
    BookNotFoundError,
    BranchNotFoundError,
    CopyNotFoundError,
    DuplicateResourceError,
    DuplicateUserError,
    InsufficientInputError,
    InvalidStateTransitionError,
    OptimisticLockConflictError,
    PermissionDeniedError,
    TransferError,
    UserNotFoundError,
)


def test_not_found_messages() -> None:
    assert "Book 'B-1' not found." in str(BookNotFoundError("B-1"))
    assert "User 'U-1' not found." in str(UserNotFoundError("U-1"))
    assert "Book copy 'C-1' not found." in str(CopyNotFoundError("C-1"))
    assert "Branch 'BR-1' not found." in str(BranchNotFoundError("BR-1"))


def test_duplicate_messages() -> None:
    err = DuplicateResourceError("Book", "B-1")
    assert err.resource_type == "Book" and err.resource_id == "B-1"
    assert "already exists." in str(err)
    dup = DuplicateUserError("U-1")
    assert "User 'U-1' already exists." in str(dup)


def test_invalid_state_transition_carries_state() -> None:
    err = InvalidStateTransitionError("cannot issue", state="RESERVED")
    assert err.state == "RESERVED"
    assert str(err) == "cannot issue"


def test_optimistic_lock_reports_versions() -> None:
    err = OptimisticLockConflictError("DOC-1", expected=1, actual=2)
    assert err.expected_version == 1 and err.actual_version == 2
    assert "expected version 1, found 2." in str(err)


def test_permission_denied_with_and_without_role() -> None:
    plain = PermissionDeniedError("BOOK_ISSUE")
    assert "Missing required permission: 'BOOK_ISSUE'." in str(plain)
    with_role = PermissionDeniedError("BOOK_ISSUE", role="STUDENT")
    assert with_role.role == "STUDENT"
    assert "Caller role: STUDENT." in str(with_role)


def test_insufficient_input_carries_detail() -> None:
    err = InsufficientInputError("nope", cause=ValueError("bad"))
    assert err.detail == "nope"
    assert str(err) == "nope"


def test_transfer_error_with_id() -> None:
    err = TransferError("transfer failed", transfer_id="TF-9")
    assert err.transfer_id == "TF-9"
    assert str(err) == "transfer failed"