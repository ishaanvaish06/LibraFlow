"""
In-memory repository implementations.

Fast, deterministic and thread-safe. Used by the unit test suite and as the
offline-development fallback. Objects returned are live references: mutating
them and re-saving updates the store.

The in-memory store provides real concurrency safety for the copy checkout
path via per-copy ``threading.Lock`` objects scoped to the mutation block.
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional

from libflow.core.book import Book, BookCopy, PhysicalBook
from libflow.core.branch import LibraryBranch
from libflow.core.user import User
from libflow.storage.repository import (
    BookRepository,
    BranchRepository,
    CirculationRecordRepository,
    UserRepository,
)


class InMemoryBookRepository(BookRepository):
    def __init__(self, lock_manager: Optional[Any] = None) -> None:
        self.books: Dict[str, Book] = {}
        self.copies: Dict[str, BookCopy] = {}
        self.lock_manager = lock_manager
        self._copy_locks: Dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()

    def _lock_for(self, copy_id: str) -> threading.Lock:
        with self._locks_guard:
            lock = self._copy_locks.get(copy_id)
            if lock is None:
                lock = threading.Lock()
                self._copy_locks[copy_id] = lock
            return lock

    def save_book(self, book: Book, session: Any = None) -> None:
        self.books[book.isbn] = book
        if isinstance(book, PhysicalBook):
            for copy in book.copies.values():
                self.copies[copy.copy_id] = copy

    def get_book(self, isbn: str, session: Any = None) -> Optional[Book]:
        return self.books.get(isbn)

    def list_books(self, session: Any = None) -> List[Book]:
        return list(self.books.values())

    def delete_book(self, isbn: str, session: Any = None) -> None:
        book = self.books.pop(isbn, None)
        if isinstance(book, PhysicalBook):
            for copy_id in list(book.copies.keys()):
                self.copies.pop(copy_id, None)

    def save_copy(self, copy: BookCopy, session: Any = None) -> None:
        self.copies[copy.copy_id] = copy
        parent = self.books.get(copy.book_isbn)
        if isinstance(parent, PhysicalBook):
            parent.copies[copy.copy_id] = copy

    def get_copy(self, copy_id: str, session: Any = None) -> Optional[BookCopy]:
        return self.copies.get(copy_id)

    def list_copies(self, session: Any = None) -> List[BookCopy]:
        return list(self.copies.values())

    def count_copies_for_isbn(self, isbn: str, session: Any = None) -> int:
        return sum(1 for c in self.copies.values() if c.book_isbn == isbn)

    @contextmanager
    def locking_section(self, copy_id: str) -> Iterator[Any]:
        if self.lock_manager is not None:
            with self.lock_manager.acquire_pessimistic_lock(copy_id):
                yield None
        else:
            lock = self._lock_for(copy_id)
            if not lock.acquire(timeout=5.0):
                raise TimeoutError(f"Could not acquire in-memory lock for copy '{copy_id}'.")
            try:
                yield None
            finally:
                lock.release()


class InMemoryUserRepository(UserRepository):
    def __init__(self) -> None:
        self.users: Dict[str, User] = {}
        self._guard = threading.Lock()

    def save_user(self, user: User, session: Any = None) -> None:
        with self._guard:
            self.users[user.user_id] = user

    def get_user(
        self, user_id: str, session: Any = None, for_update: bool = False
    ) -> Optional[User]:
        with self._guard:
            return self.users.get(user_id)

    def list_users(self, session: Any = None) -> List[User]:
        with self._guard:
            return list(self.users.values())

    def user_exists(self, user_id: str, session: Any = None) -> bool:
        with self._guard:
            return user_id in self.users


class InMemoryBranchRepository(BranchRepository):
    def __init__(self) -> None:
        self.branches: Dict[str, LibraryBranch] = {}

    def save_branch(self, branch: LibraryBranch, session: Any = None) -> None:
        self.branches[branch.branch_id] = branch

    def get_branch(self, branch_id: str, session: Any = None) -> Optional[LibraryBranch]:
        return self.branches.get(branch_id)

    def list_branches(self, session: Any = None) -> List[LibraryBranch]:
        return list(self.branches.values())


class InMemoryCirculationRecordRepository(CirculationRecordRepository):
    def __init__(self) -> None:
        self.records: List[Dict[str, Any]] = []
        self._guard = threading.Lock()

    def save_record(self, record: Dict[str, Any], session: Any = None) -> None:
        with self._guard:
            self.records.append(dict(record))

    def list_records(self, session: Any = None) -> List[Dict[str, Any]]:
        with self._guard:
            return [dict(r) for r in self.records]

    def count(self, session: Any = None) -> int:
        with self._guard:
            return len(self.records)


def build_in_memory_repositories() -> List[Any]:
    """Returns the four in-memory repositories wired for use in a container."""
    return [
        InMemoryBookRepository(),
        InMemoryUserRepository(),
        InMemoryBranchRepository(),
        InMemoryCirculationRecordRepository(),
    ]
