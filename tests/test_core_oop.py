"""
Unit Tests for Phase 1: Core Domain Modeling, OOP Hierarchy & State Transitions
"""
import pytest
from datetime import date
from libflow.core import (
    BookFormat,
    BookStatus,
    UserRole,
    PhysicalBook,
    EBook,
    AudioBook,
    BookCopy,
    Student,
    Faculty,
    Librarian,
    Admin,
    BookFactory,
    UserFactory,
    AvailableState,
    IssuedState,
    ReservedState,
    InTransitState,
    LostState,
    UnderRepairState,
)


def test_book_factory_creates_physical_book():
    book = BookFactory.create_book(
        format_type="PHYSICAL",
        isbn="978-0132350884",
        title="Clean Code",
        authors=["Robert C. Martin"],
        category="Software Engineering",
        publication_year=2008,
        weight_grams=650,
        page_count=464,
    )
    assert isinstance(book, PhysicalBook)
    assert book.get_format() == BookFormat.PHYSICAL
    assert book.isbn == "978-0132350884"
    assert book.is_available() is False  # No copies added yet

    copy1 = BookCopy(copy_id="COPY-001", book_isbn=book.isbn, branch_id="BRANCH-DELHI")
    book.add_copy(copy1)
    assert book.total_copies == 1
    assert book.is_available() is True
    assert len(book.get_available_copies()) == 1


def test_book_factory_creates_ebook_and_audiobook():
    ebook = BookFactory.create_book(
        format_type=BookFormat.EBOOK,
        isbn="978-0134685991",
        title="Effective Java",
        authors=["Joshua Bloch"],
        category="Programming",
        file_size_mb=8.4,
        max_concurrent_downloads=2,
    )
    assert isinstance(ebook, EBook)
    assert ebook.get_format() == BookFormat.EBOOK
    assert ebook.is_available() is True

    url1 = ebook.acquire_read_access()
    assert "https://" in url1
    assert ebook.active_readers_count == 1

    url2 = ebook.acquire_read_access()
    assert ebook.active_readers_count == 2
    assert ebook.is_available() is False

    with pytest.raises(ValueError, match="Max concurrent download limit"):
        ebook.acquire_read_access()

    ebook.release_read_access()
    assert ebook.is_available() is True

    audio = BookFactory.create_book(
        format_type="AUDIOBOOK",
        isbn="978-0134494166",
        title="Clean Architecture Audio",
        authors=["Robert C. Martin"],
        duration_minutes=480,
    )
    assert isinstance(audio, AudioBook)
    assert audio.get_format() == BookFormat.AUDIOBOOK


def test_book_copy_state_transitions():
    copy = BookCopy(copy_id="COPY-101", book_isbn="978-0132350884")
    assert copy.status == BookStatus.AVAILABLE

    # Available -> Issued
    copy.check_out("USER-1")
    assert copy.status == BookStatus.ISSUED
    assert copy.current_borrower_id == "USER-1"
    assert copy.borrow_count == 1

    # Cannot checkout already issued copy
    with pytest.raises(ValueError, match="Cannot checkout"):
        copy.check_out("USER-2")

    # Issued -> Available
    copy.return_book()
    assert copy.status == BookStatus.AVAILABLE
    assert copy.current_borrower_id is None

    # Available -> Reserved
    copy.reserve("USER-2")
    assert copy.status == BookStatus.RESERVED
    assert copy.current_reserver_id == "USER-2"

    # Only reserver can check out
    with pytest.raises(ValueError, match="reserved for user 'USER-2'"):
        copy.check_out("USER-3")

    copy.check_out("USER-2")
    assert copy.status == BookStatus.ISSUED
    assert copy.current_borrower_id == "USER-2"
    assert copy.current_reserver_id is None

    # Return and mark lost/repair
    copy.return_book()
    copy.mark_lost()
    assert copy.status == BookStatus.LOST

    copy.restore_available()
    assert copy.status == BookStatus.AVAILABLE


def test_user_hierarchy_and_rbac():
    student = UserFactory.create_user(
        role="STUDENT",
        user_id="STU-001",
        name="Ishaan",
        email="ishaan@example.com",
        academic_year=3,
        exam_date="2026-09-15",
    )
    assert isinstance(student, Student)
    assert student.get_role() == UserRole.STUDENT
    assert student.academic_year == 3
    assert student.exam_date == date(2026, 9, 15)
    assert student.has_permission("BOOK_SEARCH") is True
    assert student.has_permission("BOOK_MANAGE_INVENTORY") is False

    librarian = UserFactory.create_user(
        role=UserRole.LIBRARIAN,
        user_id="LIB-001",
        name="Sarah",
        email="sarah@library.org",
    )
    assert isinstance(librarian, Librarian)
    assert librarian.has_permission("BOOK_ISSUE") is True
    assert librarian.has_permission("BOOK_MANAGE_INVENTORY") is True

    admin = UserFactory.create_user(
        role=UserRole.ADMIN,
        user_id="ADM-001",
        name="Admin Chief",
        email="admin@library.org",
    )
    assert isinstance(admin, Admin)
    assert admin.has_permission("ANY_RANDOM_PERMISSION") is True  # ALL permissions


def test_user_borrowing_and_fines():
    student = Student(user_id="S1", name="Alice", email="alice@test.com", max_borrow_limit=2)
    assert student.can_borrow() is True

    student.add_borrow("COPY-1", "ISBN-1")
    assert student.can_borrow() is True
    student.add_borrow("COPY-2", "ISBN-2")
    assert student.can_borrow() is False  # Reached limit

    student.record_return("COPY-1")
    assert student.can_borrow() is True

    # Fines threshold
    student.add_fine(150.0)
    assert student.unpaid_fines_balance == 150.0
    assert student.can_borrow() is False

    paid = student.pay_fine(100.0)
    assert paid == 100.0
    assert student.unpaid_fines_balance == 50.0
    assert student.can_borrow() is True  # Below threshold of 100
