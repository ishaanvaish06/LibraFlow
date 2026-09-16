"""
Inverted Index & Ranked Multi-Criteria Search Engine
"""
from typing import Dict, Set, List, Any, Optional
import re
import math
from collections import defaultdict
from libflow.core.book import Book


class InvertedIndex:
    """
    In-memory Inverted Index providing tokenized multi-field search with TF-IDF style ranking.
    """

    def __init__(self):
        # term -> set of book ISBNs
        self.index: Dict[str, Set[str]] = defaultdict(set)
        # isbn -> term frequency map: {isbn: {term: count}}
        self.doc_term_freq: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        # isbn -> Book object
        self.books: Dict[str, Book] = {}
        # isbn -> total token count
        self.doc_lengths: Dict[str, int] = defaultdict(int)

    def _tokenize(self, text: str) -> List[str]:
        if not text:
            return []
        # Lowercase, alphanumeric extraction
        return re.findall(r"\b[a-zA-Z0-9_#\+\.\-]+\b", text.lower())

    def index_book(self, book: Book) -> None:
        """
        Indexes a book across title, authors, category, description, keywords, and ISBN.
        """
        self.books[book.isbn] = book
        # Clear existing entries for re-indexing
        for term in list(self.doc_term_freq[book.isbn].keys()):
            self.index[term].discard(book.isbn)
        self.doc_term_freq[book.isbn].clear()

        # Combine searchable texts with field boosting
        tokens: List[str] = []

        # Exact ISBN token
        tokens.extend([book.isbn.lower().replace("-", ""), book.isbn.lower()])

        # Title tokens (boosted x3)
        title_tokens = self._tokenize(book.title)
        tokens.extend(title_tokens * 3)

        # Author tokens (boosted x2)
        for author in book.authors:
            tokens.extend(self._tokenize(author) * 2)

        # Category tokens (boosted x2)
        tokens.extend(self._tokenize(book.category) * 2)

        # Keyword tokens (boosted x2)
        for kw in book.keywords:
            tokens.extend(self._tokenize(kw) * 2)

        # Description tokens
        tokens.extend(self._tokenize(book.description))

        self.doc_lengths[book.isbn] = len(tokens)

        for token in tokens:
            self.index[token].add(book.isbn)
            self.doc_term_freq[book.isbn][token] += 1

    def remove_book(self, isbn: str) -> None:
        self.books.pop(isbn, None)
        terms = list(self.doc_term_freq.get(isbn, {}).keys())
        for term in terms:
            doc_set = self.index.get(term)
            if doc_set is not None:
                doc_set.discard(isbn)
                if not doc_set:
                    del self.index[term]
        self.doc_term_freq.pop(isbn, None)
        self.doc_lengths.pop(isbn, None)

    def search(
        self,
        query: str,
        category: Optional[str] = None,
        author: Optional[str] = None,
        min_rating: Optional[float] = None,
        only_available: bool = False,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Executes a ranked multi-attribute search across the indexed library catalog.
        """
        query_tokens = self._tokenize(query)
        if not query_tokens and not (category or author or min_rating is not None or only_available):
            return []

        # Candidate selection
        candidate_isbns: Set[str] = set()
        if query_tokens:
            for token in query_tokens:
                candidate_isbns.update(self.index.get(token, set()))
        else:
            candidate_isbns = set(self.books.keys())

        ranked_results: List[Dict[str, Any]] = []
        total_docs = max(1, len(self.books))

        for isbn in candidate_isbns:
            book = self.books.get(isbn)
            if not book:
                continue

            # Multi-criteria filtering
            if category and category.lower() not in book.category.lower():
                continue
            if author and not any(author.lower() in a.lower() for a in book.authors):
                continue
            if min_rating is not None and book.rating < min_rating:
                continue
            if only_available and not book.is_available():
                continue

            # Calculate BM25 / TF-IDF relevance score
            relevance_score = 0.0
            doc_len = self.doc_lengths.get(isbn, 1)

            for token in query_tokens:
                tf = self.doc_term_freq[isbn].get(token, 0)
                if tf > 0:
                    df = len(self.index.get(token, set()))
                    idf = math.log((total_docs - df + 0.5) / (df + 0.5) + 1.0)
                    relevance_score += (tf / doc_len) * idf

            # Rating boost & availability bonus
            final_score = relevance_score + (book.rating * 0.1)
            if book.is_available():
                final_score += 0.5

            ranked_results.append({
                "book": book,
                "score": round(final_score, 4),
            })

        # Sort descending by calculated score
        ranked_results.sort(key=lambda x: x["score"], reverse=True)
        return ranked_results[:limit]
