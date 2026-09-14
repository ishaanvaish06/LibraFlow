"""
PostgreSQL repository integration tests.

Exercised against a real Postgres (see ``docker-compose.test.yml``). The
concurrency test proves that ``locking_section`` (``SELECT ... FOR UPDATE``)
provides mutual exclusion: with 50 racing threads only one wins the issue.
"""

from __future__ import annotations

import os
import threading

import pytest

from libflow.core.book import BookCopy, PhysicalBook
from libflow.core.branch import LibraryBranch
from libflow.core.factory import BookFactory, UserFactory
from libflow.core.user import User
from libflow.storage.models import BookCopyModel
from libflow.storage.postgres import (
    PostgresBookRepository,
    PostgresBranchRepository,
    PostgresCirculationRecordRepository,
    PostgresUserRepository,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.getenv("TEST_DATABASE_URL"),
        reason="TEST_DATABASE_URL not set (requires a running Postgres)",
    ),
]


def _book(isbn: str, copy_id: str = "COPY-1") -> PhysicalBook:
    book = BookFactory.create_book(isbn=isbn, format="physical")
    book.add_copy(
        BookCopy(copy_id=copy_id, book_isbn=isbn, branch_id="BR-INT")
    )
    return book


def test_book_user_branch_circulation_round_trip(session_factory) -> None:
    book_repo = PostgresBookRepository(session_factory)
    user_repo = PostgresUserRepository(session_factory)
    branch_repo = PostgresBranchRepository(session_factory)
    record_repo = PostgresCirculationRecordRepository(session_factory)

    branch = LibraryBranch(
        branch_id="BR-INT",
        name="Integration Branch",
        city="Pune",
        address="1 Test Road",
        phone="+91 9000000000",
        latitude=18.5204,
        longitude=73.8567,
    )
    branch_repo.save_branch(branch)
    assert branch_repo.get_branch("BR-INT") == branch

    book = _book("IB-100")
    book_repo.save_book(book)
    loaded = book_repo.get_book("IB-100")
    assert loaded is not None
    assert loaded.isbn == "IB-100"
    assert len(loaded.copies) == 1

    user: User = UserFactory.create_user(
        role="librarian", user_id="U-INT", name="Integration Admin",
        email="int@example.com", branch_id="BR-INT", staff_code="SC-1",
    )
    user_repo.save_user(user)
    assert user_repo.get_user("U-INT").name == "Integration Admin"

    record_repo.save_record({
        "transaction_id": "TXN-INT-1",
        "type": "ISSUE",
        "copy_id": next(iter(loaded.copies)),
        "isbn": "IB-100",
        "user_id": "U-INT",
        "borrowed_at": "2026-09-01T10:00:00",
        "due_date": "2026-09-15T10:00:00",
        "returned_at": None,
        "is_late": False,
        "is_damaged": False,
    })
    assert record_repo.count() >= 1

    user_repo.save_user(user)
    user_repo.save_user(user)  # idempotent merge
    assert len(user_repo.list_users()) >= 1
    book_repo.save_book(book)  # idempotent re-save of an existing ISBN
    loaded2 = book_repo.get_book("IB-100")
    assert loaded2 is not None and len(loaded2.copies) == 1


def test_locking_section_allows_exactly_one_writer(session_factory) -> None:
    book_repo = PostgresBookRepository(session_factory)
    copy_id = "COPY-LOCK"

    book = _book("IB-LOCK", copy_id=copy_id)
    book_repo.save_book(book)
    assert book_repo.get_copy(copy_id).status.value == "AVAILABLE"

    results = {"issued": 0, "already_checked_out": 0}
    barrier = threading.Barrier(50)

    def try_issue(copy_id_from_repo: str) -> None:
        from libflow.core.enums import BookStatus

        barrier.wait()
        try:
            with book_repo.locking_section(copy_id_from_repo) as session:
                row = session.get(BookCopyModel, copy_id_from_repo)
                if row is None or row.status != BookStatus.AVAILABLE.value:
                    results["already_checked_out"] += 1
                    return
                row.status = BookStatus.ISSUED.value
                row.current_borrower_id = "U-INT"
            results["issued"] += 1
        except Exception:
            results["already_checked_out"] += 1

    threads = [threading.Thread(target=try_issue, args=(copy_id,)) for _ in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert results["issued"] == 1
    assert results["already_checked_out"] == 49

    final = book_repo.get_copy(copy_id)
    assert final.status.value == "ISSUED"
    assert final.current_borrower_id == "U-INT"