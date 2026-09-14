"""
Hybrid Book Recommendation Engine

Combines:
1. User category-preferences vs. book content vectors (cosine similarity)
2. Graph topology proximity (co-borrow / similarity edges)

This is content + graph similarity scoring — documented plainly in
docs/ARCHITECTURE.md. It is deliberately *not* marketed as deep learning.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set

from libflow.core.book import Book
from libflow.core.user import User
from libflow.dsa.graph import BookGraphEngine


class RecommendationEngine:
    """Content + graph similarity recommender."""

    def __init__(self, graph_engine: Optional[BookGraphEngine] = None):
        self.graph_engine = graph_engine or BookGraphEngine()
        self.books: Dict[str, Book] = {}
        self.user_history: Dict[str, Set[str]] = defaultdict(set)
        self.user_category_weights: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))

    def register_book(self, book: Book) -> None:
        self.books[book.isbn] = book
        self.graph_engine.add_book_node(book.isbn, book.title, book.category, book.rating)

    def record_user_interaction(self, user_id: str, isbn: str, rating: Optional[float] = None) -> None:
        self.user_history[user_id].add(isbn)
        book = self.books.get(isbn)
        if book:
            weight = (rating / 5.0) if rating else 1.0
            self.user_category_weights[user_id][book.category] += weight
            for kw in book.keywords:
                self.user_category_weights[user_id][kw] += weight * 0.5

    def _cosine_similarity(self, vec1: Dict[str, float], vec2: Dict[str, float]) -> float:
        intersection = set(vec1.keys()) & set(vec2.keys())
        if not intersection:
            return 0.0
        dot_product = sum(vec1[k] * vec2[k] for k in intersection)
        mag1 = math.sqrt(sum(v * v for v in vec1.values()))
        mag2 = math.sqrt(sum(v * v for v in vec2.values()))
        if mag1 == 0.0 or mag2 == 0.0:
            return 0.0
        return dot_product / (mag1 * mag2)

    def recommend_for_user(self, user: User, top_k: int = 5) -> List[Dict[str, Any]]:
        user_id = user.user_id
        borrowed = self.user_history.get(user_id, set())
        cat_weights = self.user_category_weights.get(user_id, {})

        candidates: Dict[str, float] = defaultdict(float)

        for isbn, book in self.books.items():
            if isbn in borrowed:
                continue

            book_vec: Dict[str, float] = {book.category: 1.5}
            for kw in book.keywords:
                book_vec[kw] = 1.0
            content_score = self._cosine_similarity(cat_weights, book_vec)

            graph_score = 0.0
            for b_isbn in borrowed:
                for related in self.graph_engine.get_related_recommendations(b_isbn, top_k=5):
                    if related["isbn"] == isbn:
                        graph_score = max(graph_score, related["similarity_score"])

            quality_score = (book.rating / 5.0) * 0.2
            final_score = (0.5 * content_score) + (0.35 * graph_score) + (0.15 * quality_score)
            candidates[isbn] = final_score

        sorted_candidates = sorted(candidates.items(), key=lambda x: x[1], reverse=True)[:top_k]

        results = []
        for isbn, score in sorted_candidates:
            b = self.books.get(isbn)
            if b:
                results.append({
                    "isbn": isbn,
                    "title": b.title,
                    "authors": b.authors,
                    "category": b.category,
                    "rating": b.rating,
                    "difficulty_level": b.difficulty_level,
                    "match_score": round(score, 3),
                })
        return results