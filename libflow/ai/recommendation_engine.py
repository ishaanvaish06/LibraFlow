"""
AI-Based Hybrid Book Recommendation Engine
Combines:
1. User Reading History & Category Vector Similarity
2. Content-Based Metadata Similarity
3. Graph Topology Proximity
"""
from typing import Dict, List, Set, Any, Optional
import math
from collections import defaultdict

from libflow.core.book import Book
from libflow.core.user import User
from libflow.dsa.graph import BookGraphEngine


class AIRecommendationEngine:
    """
    Hybrid Recommender Engine blending collaborative user vectors, content similarity, and graph walks.
    """

    def __init__(self, graph_engine: Optional[BookGraphEngine] = None):
        self.graph_engine = graph_engine or BookGraphEngine()
        self.books: Dict[str, Book] = {}
        # user_id -> set of borrowed ISBNs
        self.user_history: Dict[str, Set[str]] = defaultdict(set)
        # user_id -> category preference vector {category: weight}
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
                self.user_category_weights[user_id][kw] += (weight * 0.5)

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
        """
        Generates top-k personalized recommendations for a user.
        """
        user_id = user.user_id
        borrowed = self.user_history.get(user_id, set())
        cat_weights = self.user_category_weights.get(user_id, {})

        candidates: Dict[str, float] = defaultdict(float)

        for isbn, book in self.books.items():
            if isbn in borrowed:
                continue  # Don't recommend already read books

            # 1. Content & Category Preference Score
            book_vec: Dict[str, float] = {book.category: 1.5}
            for kw in book.keywords:
                book_vec[kw] = 1.0

            content_score = self._cosine_similarity(cat_weights, book_vec)

            # 2. Graph Connectivity Score
            graph_score = 0.0
            for b_isbn in borrowed:
                recs = self.graph_engine.get_related_recommendations(b_isbn, top_k=5)
                for r in recs:
                    if r["isbn"] == isbn:
                        graph_score = max(graph_score, r["similarity_score"])

            # 3. Rating & Quality Boost
            quality_score = (book.rating / 5.0) * 0.2

            # Hybrid weighted combination
            final_score = (0.5 * content_score) + (0.35 * graph_score) + (0.15 * quality_score)
            candidates[isbn] = final_score

        # Sort candidates descending
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
