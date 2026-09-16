"""
SQLAlchemy ORM models for LibraFlow persistence.

Table-per-class is deliberately avoided: books and users use single-table
inheritance with nullable, format/role-specific columns. This keeps the
inventory small and the mapping layer explicit, which is a reasonable
trade-off for this domain (see docs/DECISIONS.md).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class BookModel(Base):
    __tablename__ = "books"

    isbn: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    authors: Mapped[list] = mapped_column(JSONB, default=list)
    category: Mapped[str] = mapped_column(String(128), default="General")
    publication_year: Mapped[int] = mapped_column(Integer, default=2024)
    publisher: Mapped[str] = mapped_column(String(256), default="Unknown")
    description: Mapped[str] = mapped_column(Text, default="")
    rating: Mapped[float] = mapped_column(Float, default=4.0)
    difficulty_level: Mapped[str] = mapped_column(String(64), default="Intermediate")
    keywords: Mapped[list] = mapped_column(JSONB, default=list)
    borrow_history_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Single-table inheritance discriminator
    format: Mapped[str] = mapped_column(String(16), nullable=False)

    # PhysicalBook columns
    weight_grams: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # EBook columns
    download_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    file_size_mb: Mapped[float | None] = mapped_column(Float, nullable=True)
    file_format: Mapped[str | None] = mapped_column(String(16), nullable=True)
    drm_protected: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    max_concurrent_downloads: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active_readers_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # AudioBook columns
    stream_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    narrator: Mapped[str | None] = mapped_column(String(256), nullable=True)


class BookCopyModel(Base):
    __tablename__ = "book_copies"

    copy_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    book_isbn: Mapped[str] = mapped_column(
        ForeignKey("books.isbn", ondelete="CASCADE"), index=True, nullable=False
    )
    branch_id: Mapped[str] = mapped_column(
        ForeignKey("library_branches.branch_id"), index=True, nullable=False
    )
    shelf_location: Mapped[str] = mapped_column(String(64), default="A1-01")
    price: Mapped[float] = mapped_column(Float, default=500.0)
    status: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    current_borrower_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    current_reserver_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_branch_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    borrow_count: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class UserModel(Base):
    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    email: Mapped[str] = mapped_column(String(256), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    role: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    max_borrow_limit: Mapped[int] = mapped_column(Integer, default=3)
    branch_id: Mapped[str] = mapped_column(
        ForeignKey("library_branches.branch_id"), index=True, nullable=True
    )

    active_borrowed_copy_ids: Mapped[list] = mapped_column(JSONB, default=list)
    borrow_history: Mapped[list] = mapped_column(JSONB, default=list)
    active_reservations: Mapped[list] = mapped_column(JSONB, default=list)
    unpaid_fines_balance: Mapped[float] = mapped_column(Float, default=0.0)
    security_deposit_balance: Mapped[float] = mapped_column(Float, default=0.0)
    is_suspended: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Student columns
    academic_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    major: Mapped[str | None] = mapped_column(String(128), nullable=True)
    exam_date: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Faculty column
    department: Mapped[str | None] = mapped_column(String(256), nullable=True)

    # Librarian column
    staff_code: Mapped[str | None] = mapped_column(String(64), nullable=True)


class LibraryBranchModel(Base):
    __tablename__ = "library_branches"

    branch_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    city: Mapped[str] = mapped_column(String(128), default="")
    address: Mapped[str] = mapped_column(String(512), default="")
    phone: Mapped[str] = mapped_column(String(64), default="")
    latitude: Mapped[float] = mapped_column(Float, default=0.0)
    longitude: Mapped[float] = mapped_column(Float, default=0.0)


class CirculationRecordModel(Base):
    __tablename__ = "circulation_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transaction_id: Mapped[str] = mapped_column(String(64), index=True)
    type: Mapped[str] = mapped_column(String(32))
    copy_id: Mapped[str] = mapped_column(String(64), nullable=False)
    isbn: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    borrowed_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    due_date: Mapped[str | None] = mapped_column(String(64), nullable=True)
    returned_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_late: Mapped[bool] = mapped_column(Boolean, default=False)
    is_damaged: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class OutboxEventModel(Base):
    """
    Transactional Outbox Table.
    Guarantees at-least-once event delivery by committing events atomically
    within the same relational transaction as business state changes.
    """
    __tablename__ = "outbox_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    topic: Mapped[str] = mapped_column(String(128), index=True)
    payload: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(32), default="PENDING", index=True)  # PENDING, PUBLISHED, FAILED
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
