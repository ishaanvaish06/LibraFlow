"""
Catalog Service: orchestrates book creation, indexing, autocomplete and caching.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from libflow.core.book import Book, BookCopy, PhysicalBook
from libflow.core.exceptions import BookNotFoundError
from libflow.core.factory import BookFactory
from libflow.dsa.inverted_index import InvertedIndex
from libflow.dsa.trie import AutocompleteTrie
from libflow.patterns.singleton_logger import AuditLogger
from libflow.storage.cache import Cache
from libflow.storage.repository import BookRepository


class CatalogService:
    def __init__(
        self,
        book_repo: BookRepository,
        trie: AutocompleteTrie,
        index: InvertedIndex,
        cache: Cache,
    ):
        self.book_repo = book_repo
        self.trie = trie
        self.index = index
        self.cache = cache
        self.audit_logger = AuditLogger()

    def register_book(self, format_type: str, actor_id: str, **kwargs: Any) -> Book:
        book = BookFactory.create_book(format_type=format_type, **kwargs)
        self.book_repo.save_book(book)

        self.index.index_book(book)
        self.trie.insert(book.title, book.isbn, book.title, weight=book.rating)
        for author in book.authors:
            self.trie.insert(author, book.isbn, f"{book.title} (by {author})", weight=book.rating * 0.9)

        self.cache.invalidate_prefix("search:")
        self.cache.invalidate(f"book:{book.isbn}")

        self.audit_logger.log_event(
            actor_id=actor_id,
            action="CREATE_BOOK",
            resource_id=book.isbn,
            details={"title": book.title, "format": book.get_format().value},
        )
        return book

    def add_physical_copy(
        self,
        isbn: str,
        copy_id: str,
        branch_id: str = "BRANCH-DELHI",
        shelf_location: str = "A1-01",
        price: float = 500.0,
        actor_id: str = "ADMIN",
    ) -> BookCopy:
        book = self.book_repo.get_book(isbn)
        if not isinstance(book, PhysicalBook):
            raise BookNotFoundError(isbn)

        copy = BookCopy(
            copy_id=copy_id,
            book_isbn=isbn,
            branch_id=branch_id,
            shelf_location=shelf_location,
            price=price,
        )
        book.add_copy(copy)
        self.book_repo.save_copy(copy)
        self.book_repo.save_book(book)

        self.cache.invalidate(f"book:{isbn}")

        self.audit_logger.log_event(
            actor_id=actor_id,
            action="ADD_BOOK_COPY",
            resource_id=copy_id,
            details={"isbn": isbn, "branch_id": branch_id},
        )
        return copy

    def get_book_details(self, isbn: str) -> Optional[Dict[str, Any]]:
        cache_key = f"book:{isbn}"

        def _loader() -> Optional[Dict[str, Any]]:
            book = self.book_repo.get_book(isbn)
            return book.to_dict() if book else None

        return self.cache.get_or_compute(cache_key, _loader, ttl_seconds=600.0)

    def search_books(
        self,
        query: str,
        category: Optional[str] = None,
        author: Optional[str] = None,
        min_rating: Optional[float] = None,
        only_available: bool = False,
    ) -> List[Dict[str, Any]]:
        results = self.index.search(
            query=query,
            category=category,
            author=author,
            min_rating=min_rating,
            only_available=only_available,
        )
        return [{"book": r["book"].to_dict(), "relevance_score": r["score"]} for r in results]

    def autocomplete(self, prefix: str, limit: int = 8) -> List[Dict[str, Any]]:
        return self.trie.search_prefix(prefix=prefix, limit=limit)
