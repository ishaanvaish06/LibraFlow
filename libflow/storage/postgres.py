"""
PostgreSQL repository implementations via SQLAlchemy.

Mapped repositories translate between ORM rows and the domain objects the
services consume. Writes made inside a ``locking_section`` (checkout/return)
run against the same transaction, giving real atomicity backed by
``SELECT ... FOR UPDATE``.

Mappings are intentionally explicit: every field is read or written in one
place, which keeps surprising persistence behaviour out of the domain layer.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.engine import Engine

from libflow.core.book import Book, BookCopy, PhysicalBook, EBook, AudioBook
from libflow.core.branch import LibraryBranch
from libflow.core.enums import BookFormat, UserRole
from libflow.core.factory import UserFactory
from libflow.core.user import User
from libflow.storage.models import (
    Base,
    BookCopyModel,
    BookModel,
    CirculationRecordModel,
    LibraryBranchModel,
    UserModel,
)
from libflow.storage.repository import (
    BookRepository,
    BranchRepository,
    CirculationRecordRepository,
    UserRepository,
)

_FORMAT_TO_NAME = {
    BookFormat.PHYSICAL: "PHYSICAL",
    BookFormat.EBOOK: "EBOOK",
    BookFormat.AUDIOBOOK: "AUDIOBOOK",
}


class DatabaseSessionFactory:
    """Owns the SQLAlchemy engine and sessionmaker for a Postgres database."""

    def __init__(self, url: str, engine: Optional[Engine] = None):
        self.engine = engine
        self.initialize(url)

    def initialize(self, url: str) -> None:
        from sqlalchemy import create_engine

        self.engine = create_engine(
            url,
            pool_pre_ping=True,
            future=True,
        )
        self._session_factory = sessionmaker(
            bind=self.engine, class_=Session, expire_on_commit=False
        )

    def create_session(self) -> Session:
        return self._session_factory()

    def create_all(self) -> None:
        Base.metadata.create_all(self.engine)

    def dispose(self) -> None:
        if self.engine is not None:
            self.engine.dispose()


# ---------------------------------------------------------------------------
# Mapping helpers
# ---------------------------------------------------------------------------

def book_to_model(book: Book) -> BookModel:
    fmt = _FORMAT_TO_NAME[book.get_format()]
    model = BookModel(
        isbn=book.isbn,
        title=book.title,
        authors=list(book.authors),
        category=book.category,
        publication_year=book.publication_year,
        publisher=book.publisher,
        description=book.description,
        rating=book.rating,
        difficulty_level=book.difficulty_level,
        keywords=list(book.keywords),
        borrow_history_count=book.borrow_history_count,
        format=fmt,
    )
    if isinstance(book, PhysicalBook):
        model.weight_grams = book.weight_grams
        model.page_count = book.page_count
    elif isinstance(book, EBook):
        model.download_url = book.download_url
        model.file_size_mb = book.file_size_mb
        model.file_format = book.file_format
        model.drm_protected = book.drm_protected
        model.max_concurrent_downloads = book.max_concurrent_downloads
        model.active_readers_count = book.active_readers_count
    elif isinstance(book, AudioBook):
        model.stream_url = book.stream_url
        model.duration_minutes = book.duration_minutes
        model.narrator = book.narrator
    return model


def model_to_book(model: BookModel, copies: Optional[List[BookCopy]] = None) -> Book:
    common = dict(
        isbn=model.isbn,
        title=model.title,
        authors=list(model.authors or []),
        category=model.category,
        publication_year=model.publication_year,
        publisher=model.publisher,
        description=model.description,
        rating=model.rating,
        difficulty_level=model.difficulty_level,
        keywords=list(model.keywords or []),
    )
    if model.format == BookFormat.PHYSICAL.value:
        book = PhysicalBook(
            weight_grams=model.weight_grams or 500,
            page_count=model.page_count or 400,
            **common,
        )
        for copy in copies or []:
            book.add_copy(copy)
    elif model.format == BookFormat.EBOOK.value:
        book = EBook(
            download_url=model.download_url or "",
            file_size_mb=model.file_size_mb or 0.0,
            file_format=model.file_format or "PDF",
            drm_protected=bool(model.drm_protected),
            max_concurrent_downloads=model.max_concurrent_downloads or 100,
            **common,
        )
        book.active_readers_count = model.active_readers_count or 0
    elif model.format == BookFormat.AUDIOBOOK.value:
        book = AudioBook(
            stream_url=model.stream_url or "",
            duration_minutes=model.duration_minutes or 0,
            narrator=model.narrator or "Narrator",
            **common,
        )
    else:
        raise ValueError(f"Unknown book format in DB: {model.format}")
    book.borrow_history_count = model.borrow_history_count or 0
    return book


def copy_to_model(copy: BookCopy) -> BookCopyModel:
    return BookCopyModel(
        copy_id=copy.copy_id,
        book_isbn=copy.book_isbn,
        branch_id=copy.branch_id,
        shelf_location=copy.shelf_location,
        price=copy.price,
        status=copy.status.value,
        current_borrower_id=copy.current_borrower_id,
        current_reserver_id=copy.current_reserver_id,
        target_branch_id=copy.target_branch_id,
        borrow_count=copy.borrow_count,
    )


def model_to_copy(model: BookCopyModel) -> BookCopy:
    copy = BookCopy(
        copy_id=model.copy_id,
        book_isbn=model.book_isbn,
        branch_id=model.branch_id,
        shelf_location=model.shelf_location,
        price=model.price,
    )
    copy.set_state(_STATUS_TO_STATE[model.status]())
    copy.current_borrower_id = model.current_borrower_id
    copy.current_reserver_id = model.current_reserver_id
    copy.target_branch_id = model.target_branch_id
    copy.borrow_count = model.borrow_count or 0
    return copy


def _map_status_to_state():
    from libflow.core.enums import BookStatus as BS
    from libflow.core.book_state import (
        AvailableState,
        ReservedState,
        IssuedState,
        InTransitState,
        UnderRepairState,
        LostState,
    )

    return {
        BS.AVAILABLE.value: AvailableState,
        BS.RESERVED.value: ReservedState,
        BS.ISSUED.value: IssuedState,
        BS.IN_TRANSIT.value: InTransitState,
        BS.UNDER_REPAIR.value: UnderRepairState,
        BS.LOST.value: LostState,
    }


_STATUS_TO_STATE = _map_status_to_state()


def user_to_model(user: User) -> UserModel:
    role = user.get_role()
    model = UserModel(
        user_id=user.user_id,
        name=user.name,
        email=user.email,
        password_hash=user.password_hash,
        role=role.value,
        max_borrow_limit=user.max_borrow_limit,
        branch_id=user.branch_id,
        active_borrowed_copy_ids=list(user.active_borrowed_copy_ids),
        borrow_history=user.borrow_history,
        active_reservations=list(user.active_reservations),
        unpaid_fines_balance=user.unpaid_fines_balance,
        security_deposit_balance=user.security_deposit_balance,
        is_suspended=user.is_suspended,
    )
    if role == UserRole.STUDENT:
        model.academic_year = user.academic_year
        model.major = user.major
        model.exam_date = user.exam_date.isoformat() if user.exam_date else None
    elif role == UserRole.FACULTY:
        model.department = user.department
    elif role == UserRole.LIBRARIAN:
        model.staff_code = user.staff_code
    return model


def model_to_user(model: UserModel) -> User:
    kwargs: Dict[str, Any] = dict(
        user_id=model.user_id,
        name=model.name,
        email=model.email,
        password_hash=model.password_hash,
        branch_id=model.branch_id,
        max_borrow_limit=model.max_borrow_limit,
    )
    if model.role == UserRole.STUDENT.value:
        kwargs.update(
            academic_year=model.academic_year or 1,
            major=model.major or "Computer Science",
            exam_date=model.exam_date,
        )
    elif model.role == UserRole.FACULTY.value:
        kwargs["department"] = model.department
    elif model.role == UserRole.LIBRARIAN.value:
        kwargs["staff_code"] = model.staff_code

    user = UserFactory.create_user(role=model.role, **kwargs)
    user.active_borrowed_copy_ids = set(model.active_borrowed_copy_ids or [])
    user.borrow_history = list(model.borrow_history or [])
    user.active_reservations = set(model.active_reservations or [])
    user.unpaid_fines_balance = float(model.unpaid_fines_balance or 0.0)
    user.security_deposit_balance = float(model.security_deposit_balance or 0.0)
    user.is_suspended = bool(model.is_suspended)
    return user


def branch_to_model(branch: LibraryBranch) -> LibraryBranchModel:
    return LibraryBranchModel(
        branch_id=branch.branch_id,
        name=branch.name,
        city=branch.city,
        address=branch.address,
        phone=branch.phone,
        latitude=branch.latitude,
        longitude=branch.longitude,
    )


def model_to_branch(model: LibraryBranchModel) -> LibraryBranch:
    return LibraryBranch(
        branch_id=model.branch_id,
        name=model.name,
        city=model.city,
        address=model.address,
        phone=model.phone,
        latitude=model.latitude,
        longitude=model.longitude,
    )


class _MappedBase:
    """Shared session-resolution plumbing for Postgres repositories."""

    session_factory: DatabaseSessionFactory

    @contextmanager
    def _session(self, session: Optional[Session]) -> Iterator[Session]:
        owns = session is None
        s: Session = session if session is not None else self.session_factory.create_session()
        try:
            yield s
            if owns:
                s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            if owns:
                s.close()


class PostgresBookRepository(_MappedBase, BookRepository):
    def __init__(self, session_factory: DatabaseSessionFactory):
        self.session_factory = session_factory

    def save_book(self, book: Book, session: Any = None) -> None:
        with self._session(session) as s:
            model = book_to_model(book)
            existing = s.get(BookModel, book.isbn)
            if existing is not None:
                existing.title = model.title
                existing.authors = model.authors
                existing.category = model.category
                existing.publication_year = model.publication_year
                existing.publisher = model.publisher
                existing.description = model.description
                existing.rating = model.rating
                existing.difficulty_level = model.difficulty_level
                existing.keywords = model.keywords
                existing.borrow_history_count = model.borrow_history_count
                existing.format = model.format
                existing.weight_grams = model.weight_grams
                existing.page_count = model.page_count
                existing.download_url = model.download_url
                existing.file_size_mb = model.file_size_mb
                existing.file_format = model.file_format
                existing.drm_protected = model.drm_protected
                existing.max_concurrent_downloads = model.max_concurrent_downloads
                existing.active_readers_count = model.active_readers_count
                existing.stream_url = model.stream_url
                existing.duration_minutes = model.duration_minutes
                existing.narrator = model.narrator
            else:
                s.add(model)
            if isinstance(book, PhysicalBook):
                for copy in book.copies.values():
                    s.merge(copy_to_model(copy))

    def get_book(self, isbn: str, session: Any = None) -> Optional[Book]:
        with self._session(session) as s:
            model = s.get(BookModel, isbn)
            if model is None:
                return None
            copies = [
                model_to_copy(c)
                for c in s.scalars(
                    select(BookCopyModel).where(BookCopyModel.book_isbn == isbn)
                )
            ]
            return model_to_book(model, copies)

    def list_books(self, session: Any = None) -> List[Book]:
        with self._session(session) as s:
            rows = s.scalars(select(BookModel)).all()
            return [model_to_book(m) for m in rows]

    def delete_book(self, isbn: str, session: Any = None) -> None:
        with self._session(session) as s:
            model = s.get(BookModel, isbn)
            if model is not None:
                s.delete(model)

    def save_copy(self, copy: BookCopy, session: Any = None) -> None:
        with self._session(session) as s:
            s.merge(copy_to_model(copy))

    def get_copy(self, copy_id: str, session: Any = None) -> Optional[BookCopy]:
        with self._session(session) as s:
            model = s.get(BookCopyModel, copy_id)
            return model_to_copy(model) if model else None

    def list_copies(self, session: Any = None) -> List[BookCopy]:
        with self._session(session) as s:
            return [model_to_copy(m) for m in s.scalars(select(BookCopyModel)).all()]

    def count_copies_for_isbn(self, isbn: str, session: Any = None) -> int:
        with self._session(session) as s:
            return len(s.scalars(
                select(BookCopyModel).where(BookCopyModel.book_isbn == isbn)
            ).all())

    @contextmanager
    def locking_section(self, copy_id: str) -> Iterator[Any]:
        """Pessimistic lock: SELECT ... FOR UPDATE on the copy row."""
        from libflow.core.exceptions import CopyNotFoundError

        s = self.session_factory.create_session()
        try:
            stmt = (
                select(BookCopyModel)
                .where(BookCopyModel.copy_id == copy_id)
                .with_for_update()
            )
            model = s.scalars(stmt).one_or_none()
            if model is None:
                raise CopyNotFoundError(copy_id)
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()


class PostgresUserRepository(_MappedBase, UserRepository):
    def __init__(self, session_factory: DatabaseSessionFactory):
        self.session_factory = session_factory

    def save_user(self, user: User, session: Any = None) -> None:
        with self._session(session) as s:
            s.merge(user_to_model(user))

    def get_user(self, user_id: str, session: Any = None) -> Optional[User]:
        with self._session(session) as s:
            model = s.get(UserModel, user_id)
            return model_to_user(model) if model else None

    def list_users(self, session: Any = None) -> List[User]:
        with self._session(session) as s:
            return [model_to_user(m) for m in s.scalars(select(UserModel)).all()]

    def user_exists(self, user_id: str, session: Any = None) -> bool:
        with self._session(session) as s:
            return s.get(UserModel, user_id) is not None


class PostgresBranchRepository(_MappedBase, BranchRepository):
    def __init__(self, session_factory: DatabaseSessionFactory):
        self.session_factory = session_factory

    def save_branch(self, branch: LibraryBranch, session: Any = None) -> None:
        with self._session(session) as s:
            s.merge(branch_to_model(branch))

    def get_branch(self, branch_id: str, session: Any = None) -> Optional[LibraryBranch]:
        with self._session(session) as s:
            model = s.get(LibraryBranchModel, branch_id)
            return model_to_branch(model) if model else None

    def list_branches(self, session: Any = None) -> List[LibraryBranch]:
        with self._session(session) as s:
            return [model_to_branch(b) for b in s.scalars(select(LibraryBranchModel)).all()]


class PostgresCirculationRecordRepository(_MappedBase, CirculationRecordRepository):
    def __init__(self, session_factory: DatabaseSessionFactory):
        self.session_factory = session_factory

    def save_record(self, record: Dict[str, Any], session: Any = None) -> None:
        with self._session(session) as s:
            s.add(CirculationRecordModel(
                transaction_id=record.get("transaction_id", ""),
                type=record.get("type", ""),
                copy_id=record.get("copy_id", ""),
                isbn=record.get("isbn", ""),
                user_id=record.get("user_id", ""),
                borrowed_at=record.get("borrowed_at"),
                due_date=record.get("due_date"),
                returned_at=record.get("returned_at"),
                is_late=bool(record.get("is_late", False)),
                is_damaged=bool(record.get("is_damaged", False)),
            ))

    def list_records(self, session: Any = None) -> List[Dict[str, Any]]:
        with self._session(session) as s:
            rows = s.scalars(select(CirculationRecordModel)).all()
            return [self._row_to_dict(r) for r in rows]

    def count(self, session: Any = None) -> int:
        with self._session(session) as s:
            return len(s.scalars(select(CirculationRecordModel)).all())

    @staticmethod
    def _row_to_dict(row: CirculationRecordModel) -> Dict[str, Any]:
        return {
            "transaction_id": row.transaction_id,
            "type": row.type,
            "copy_id": row.copy_id,
            "isbn": row.isbn,
            "user_id": row.user_id,
            "borrowed_at": row.borrowed_at,
            "due_date": row.due_date,
            "returned_at": row.returned_at,
            "is_late": row.is_late,
            "is_damaged": row.is_damaged,
        }
