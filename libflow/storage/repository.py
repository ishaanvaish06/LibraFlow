"""
Repository interfaces.

Services depend on these abstractions, never on a concrete storage class.
Two implementations exist:

* ``libflow.storage.inmemory`` — fast, deterministic, used by unit tests and
  offline development.
* ``libflow.storage.postgres`` — real persistence with SQLAlchemy.

The ``locking_section`` context manager is the single place concurrency
control lives for copy mutations: a ``threading.Lock`` per copy in the
in-memory store, ``SELECT ... FOR UPDATE`` inside a transaction in Postgres.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional

from libflow.core.book import Book, BookCopy
from libflow.core.branch import LibraryBranch
from libflow.core.user import User


class BookRepository(ABC):
    @abstractmethod
    def save_book(self, book: Book, session: Any = None) -> None:
        """Persist a book (and, for physical books, its copies)."""

    @abstractmethod
    def get_book(self, isbn: str, session: Any = None) -> Optional[Book]:
        """Return a fully-assembled book or None."""

    @abstractmethod
    def list_books(self, session: Any = None) -> List[Book]:
        ...

    @abstractmethod
    def delete_book(self, isbn: str, session: Any = None) -> None:
        ...

    @abstractmethod
    def save_copy(self, copy: BookCopy, session: Any = None) -> None:
        """Persist the current state of a copy."""

    @abstractmethod
    def get_copy(self, copy_id: str, session: Any = None) -> Optional[BookCopy]:
        ...

    @abstractmethod
    def list_copies(self, session: Any = None) -> List[BookCopy]:
        ...

    @abstractmethod
    def count_copies_for_isbn(self, isbn: str, session: Any = None) -> int:
        ...

    @contextmanager
    def locking_section(self, copy_id: str) -> Iterator[Any]:
        """
        Exclusive, scope-limited lock on ``copy_id`` for the mutation block.

        Yields an opaque handle (in-memory: ``None``; Postgres: the active
        session). The lock is released when the block exits.
        """
        yield None


class UserRepository(ABC):
    @abstractmethod
    def save_user(self, user: User, session: Any = None) -> None:
        ...

    @abstractmethod
    def get_user(self, user_id: str, session: Any = None) -> Optional[User]:
        ...

    @abstractmethod
    def list_users(self, session: Any = None) -> List[User]:
        ...

    @abstractmethod
    def user_exists(self, user_id: str, session: Any = None) -> bool:
        ...


class BranchRepository(ABC):
    @abstractmethod
    def save_branch(self, branch: LibraryBranch, session: Any = None) -> None:
        ...

    @abstractmethod
    def get_branch(self, branch_id: str, session: Any = None) -> Optional[LibraryBranch]:
        ...

    @abstractmethod
    def list_branches(self, session: Any = None) -> List[LibraryBranch]:
        ...


class CirculationRecordRepository(ABC):
    @abstractmethod
    def save_record(self, record: Dict[str, Any], session: Any = None) -> None:
        ...

    @abstractmethod
    def list_records(self, session: Any = None) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    def count(self, session: Any = None) -> int:
        ...