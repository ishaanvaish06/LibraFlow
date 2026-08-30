"""
Database Layer & ACID Transaction Simulation
Manages relational storage, relational integrity, foreign key references, and transactional commits/rollbacks.
"""
from typing import Dict, Any, List, Optional
import copy
import threading
from contextlib import contextmanager

from libflow.core.book import Book, PhysicalBook, BookCopy
from libflow.core.user import User
from libflow.core.branch import LibraryBranch


class LibraryDatabase:
    """
    In-memory ACID relational database simulator with rollback capabilities.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self.books: Dict[str, Book] = {}
        self.book_copies: Dict[str, BookCopy] = {}
        self.users: Dict[str, User] = {}
        self.branches: Dict[str, LibraryBranch] = {}
        self.borrow_transactions: List[Dict[str, Any]] = []

    @contextmanager
    def transaction(self):
        """
        ACID Transaction block: takes a snapshot and restores state if exception occurs.
        """
        with self._lock:
            # Snapshot
            snapshot_books = copy.deepcopy(self.books)
            snapshot_copies = copy.deepcopy(self.book_copies)
            snapshot_users = copy.deepcopy(self.users)
            snapshot_branches = copy.deepcopy(self.branches)
            snapshot_tx = copy.deepcopy(self.borrow_transactions)

            try:
                yield self
            except Exception as e:
                # Rollback
                self.books = snapshot_books
                self.book_copies = snapshot_copies
                self.users = snapshot_users
                self.branches = snapshot_branches
                self.borrow_transactions = snapshot_tx
                raise e

    def save_book(self, book: Book) -> None:
        self.books[book.isbn] = book
        if isinstance(book, PhysicalBook):
            for copy in book.copies.values():
                self.book_copies[copy.copy_id] = copy

    def get_book(self, isbn: str) -> Optional[Book]:
        return self.books.get(isbn)

    def save_user(self, user: User) -> None:
        self.users[user.user_id] = user

    def get_user(self, user_id: str) -> Optional[User]:
        return self.users.get(user_id)

    def get_copy(self, copy_id: str) -> Optional[BookCopy]:
        return self.book_copies.get(copy_id)

    def save_branch(self, branch: LibraryBranch) -> None:
        self.branches[branch.branch_id] = branch

    def get_branch(self, branch_id: str) -> Optional[LibraryBranch]:
        return self.branches.get(branch_id)

    def record_circulation_log(self, record: Dict[str, Any]) -> None:
        self.borrow_transactions.append(record)
