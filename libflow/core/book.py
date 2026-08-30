"""
Core Book Domain Model & Hierarchy
Demonstrating Inheritance, Polymorphism, and Encapsulation
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid

from libflow.core.enums import BookFormat, BookStatus
from libflow.core.book_state import BookCopyState, AvailableState


class BookCopy:
    """
    Represents an individual physical or trackable copy/item of a title.
    Maintains its own lifecycle state via the State Pattern.
    """

    def __init__(
        self,
        copy_id: str,
        book_isbn: str,
        branch_id: str = "BRANCH-CENTRAL",
        shelf_location: str = "A1-01",
        price: float = 500.0,
    ):
        self.copy_id = copy_id
        self.book_isbn = book_isbn
        self.branch_id = branch_id
        self.shelf_location = shelf_location
        self.price = price
        self._state: BookCopyState = AvailableState()
        self.current_borrower_id: Optional[str] = None
        self.current_reserver_id: Optional[str] = None
        self.target_branch_id: Optional[str] = None
        self.borrow_count: int = 0
        self.created_at: datetime = datetime.now()

    @property
    def status(self) -> BookStatus:
        return self._state.get_status()

    def set_state(self, state: BookCopyState) -> None:
        self._state = state

    def check_out(self, borrower_id: str) -> None:
        self._state.check_out(self, borrower_id)
        self.borrow_count += 1

    def return_book(self) -> None:
        self._state.return_book(self)

    def reserve(self, reserver_id: str) -> None:
        self._state.reserve(self, reserver_id)

    def start_transfer(self, destination_branch: str) -> None:
        self._state.start_transfer(self, destination_branch)

    def complete_transfer(self) -> None:
        self._state.complete_transfer(self)

    def mark_lost(self) -> None:
        self._state.mark_lost(self)

    def mark_repair(self) -> None:
        self._state.mark_repair(self)

    def restore_available(self) -> None:
        self._state.restore_available(self)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "copy_id": self.copy_id,
            "book_isbn": self.book_isbn,
            "branch_id": self.branch_id,
            "shelf_location": self.shelf_location,
            "price": self.price,
            "status": self.status.value,
            "current_borrower_id": self.current_borrower_id,
            "current_reserver_id": self.current_reserver_id,
            "borrow_count": self.borrow_count,
        }


class Book(ABC):
    """
    Abstract Base Class for all Book types.
    Enforces common metadata and polymorphic behavior.
    """

    def __init__(
        self,
        isbn: str,
        title: str,
        authors: List[str],
        category: str,
        publication_year: int,
        publisher: str = "Unknown",
        description: str = "",
        rating: float = 4.0,
        difficulty_level: str = "Intermediate",
        keywords: Optional[List[str]] = None,
    ):
        self.isbn = isbn
        self.title = title
        self.authors = authors
        self.category = category
        self.publication_year = publication_year
        self.publisher = publisher
        self.description = description
        self.rating = rating
        self.difficulty_level = difficulty_level
        self.keywords = keywords or []
        self.borrow_history_count: int = 0

    @abstractmethod
    def get_format(self) -> BookFormat:
        """Returns the format type (PHYSICAL, EBOOK, etc.)"""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Returns whether this book can currently be borrowed or accessed."""
        pass

    def to_dict(self) -> Dict[str, Any]:
        return {
            "isbn": self.isbn,
            "title": self.title,
            "authors": self.authors,
            "category": self.category,
            "publication_year": self.publication_year,
            "publisher": self.publisher,
            "description": self.description,
            "rating": self.rating,
            "difficulty_level": self.difficulty_level,
            "keywords": self.keywords,
            "format": self.get_format().value,
            "is_available": self.is_available(),
        }


class PhysicalBook(Book):
    """
    Physical book edition containing tangible inventory copies across branches.
    """

    def __init__(
        self,
        isbn: str,
        title: str,
        authors: List[str],
        category: str,
        publication_year: int,
        publisher: str = "Unknown",
        description: str = "",
        rating: float = 4.0,
        difficulty_level: str = "Intermediate",
        keywords: Optional[List[str]] = None,
        weight_grams: int = 500,
        page_count: int = 400,
    ):
        super().__init__(
            isbn, title, authors, category, publication_year, publisher, description, rating, difficulty_level, keywords
        )
        self.weight_grams = weight_grams
        self.page_count = page_count
        self.copies: Dict[str, BookCopy] = {}

    def get_format(self) -> BookFormat:
        return BookFormat.PHYSICAL

    def add_copy(self, copy: BookCopy) -> None:
        self.copies[copy.copy_id] = copy

    def remove_copy(self, copy_id: str) -> Optional[BookCopy]:
        return self.copies.pop(copy_id, None)

    def get_available_copies(self, branch_id: Optional[str] = None) -> List[BookCopy]:
        return [
            c for c in self.copies.values()
            if c.status == BookStatus.AVAILABLE and (branch_id is None or c.branch_id == branch_id)
        ]

    def is_available(self) -> bool:
        return len(self.get_available_copies()) > 0

    @property
    def total_copies(self) -> int:
        return len(self.copies)

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "total_copies": self.total_copies,
            "available_copies": len(self.get_available_copies()),
            "weight_grams": self.weight_grams,
            "page_count": self.page_count,
            "copies": [c.to_dict() for c in self.copies.values()],
        })
        return data


class EBook(Book):
    """
    Digital E-Book edition with direct download links and concurrent access controls.
    """

    def __init__(
        self,
        isbn: str,
        title: str,
        authors: List[str],
        category: str,
        publication_year: int,
        download_url: str,
        file_size_mb: float,
        file_format: str = "PDF",
        drm_protected: bool = True,
        max_concurrent_downloads: int = 100,
        publisher: str = "Unknown",
        description: str = "",
        rating: float = 4.0,
        difficulty_level: str = "Intermediate",
        keywords: Optional[List[str]] = None,
    ):
        super().__init__(
            isbn, title, authors, category, publication_year, publisher, description, rating, difficulty_level, keywords
        )
        self.download_url = download_url
        self.file_size_mb = file_size_mb
        self.file_format = file_format
        self.drm_protected = drm_protected
        self.max_concurrent_downloads = max_concurrent_downloads
        self.active_readers_count: int = 0

    def get_format(self) -> BookFormat:
        return BookFormat.EBOOK

    def is_available(self) -> bool:
        return self.active_readers_count < self.max_concurrent_downloads

    def acquire_read_access(self) -> str:
        if not self.is_available():
            raise ValueError(f"Max concurrent download limit ({self.max_concurrent_downloads}) reached for '{self.title}'.")
        self.active_readers_count += 1
        self.borrow_history_count += 1
        return self.download_url

    def release_read_access(self) -> None:
        if self.active_readers_count > 0:
            self.active_readers_count -= 1

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "download_url": self.download_url,
            "file_size_mb": self.file_size_mb,
            "file_format": self.file_format,
            "drm_protected": self.drm_protected,
            "active_readers": self.active_readers_count,
            "max_concurrent_downloads": self.max_concurrent_downloads,
        })
        return data


class AudioBook(Book):
    """
    Digital AudioBook edition with narrator metadata and streaming duration.
    """

    def __init__(
        self,
        isbn: str,
        title: str,
        authors: List[str],
        category: str,
        publication_year: int,
        stream_url: str,
        duration_minutes: int,
        narrator: str = "Narrator",
        publisher: str = "Unknown",
        description: str = "",
        rating: float = 4.0,
        difficulty_level: str = "Intermediate",
        keywords: Optional[List[str]] = None,
    ):
        super().__init__(
            isbn, title, authors, category, publication_year, publisher, description, rating, difficulty_level, keywords
        )
        self.stream_url = stream_url
        self.duration_minutes = duration_minutes
        self.narrator = narrator

    def get_format(self) -> BookFormat:
        return BookFormat.AUDIOBOOK

    def is_available(self) -> bool:
        return True

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "stream_url": self.stream_url,
            "duration_minutes": self.duration_minutes,
            "narrator": self.narrator,
        })
        return data
