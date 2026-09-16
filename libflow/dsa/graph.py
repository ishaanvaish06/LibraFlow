"""
Graph-Based Book Relationship & Subject Traversal Engine
Nodes: Books / Subjects
Edges: Similarity, Co-Borrow Affinity, Prerequisite Dependency
Algorithms: BFS (Shortest Connection Path), DFS (Prerequisite Learning Path)
"""
from typing import Dict, List, Set, Optional, Any
from collections import deque
from dataclasses import dataclass


@dataclass
class Edge:
    target_isbn: str
    weight: float  # Similarity or affinity score (0.0 to 1.0)
    relation_type: str = "SIMILAR_TO"  # "SIMILAR_TO", "PREREQUISITE_FOR", "CO_BORROWED"


class BookGraphEngine:
    """
    In-memory Graph Engine representing topic and book relationship networks.
    """

    def __init__(self):
        # isbn -> list of Edge
        self.adj_list: Dict[str, List[Edge]] = {}
        # isbn -> book metadata dictionary
        self.nodes_meta: Dict[str, Dict[str, Any]] = {}

    def add_book_node(self, isbn: str, title: str, category: str, rating: float = 4.0) -> None:
        if isbn not in self.adj_list:
            self.adj_list[isbn] = []
        self.nodes_meta[isbn] = {
            "isbn": isbn,
            "title": title,
            "category": category,
            "rating": rating,
        }

    def add_relation(
        self,
        from_isbn: str,
        to_isbn: str,
        weight: float = 0.8,
        relation_type: str = "SIMILAR_TO",
        bidirectional: bool = True,
    ) -> None:
        if from_isbn not in self.adj_list:
            self.add_book_node(from_isbn, f"Book {from_isbn}", "General")
        if to_isbn not in self.adj_list:
            self.add_book_node(to_isbn, f"Book {to_isbn}", "General")

        self.adj_list[from_isbn].append(Edge(target_isbn=to_isbn, weight=weight, relation_type=relation_type))
        if bidirectional:
            self.adj_list[to_isbn].append(Edge(target_isbn=from_isbn, weight=weight, relation_type=relation_type))

    def bfs_shortest_path(self, start_isbn: str, target_isbn: str) -> Optional[List[Dict[str, Any]]]:
        """
        Finds the shortest relation path between two books using BFS.
        """
        if start_isbn not in self.adj_list or target_isbn not in self.adj_list:
            return None

        visited: Set[str] = {start_isbn}
        queue: deque[List[str]] = deque([[start_isbn]])

        while queue:
            path = queue.popleft()
            current = path[-1]

            if current == target_isbn:
                return [self.nodes_meta.get(isbn, {"isbn": isbn}) for isbn in path]

            for edge in self.adj_list.get(current, []):
                if edge.target_isbn not in visited:
                    visited.add(edge.target_isbn)
                    queue.append(path + [edge.target_isbn])

        return None

    def dfs_learning_path(self, start_isbn: str, max_depth: int = 5) -> List[Dict[str, Any]]:
        """
        Explores prerequisite / deep subject learning chains using DFS.
        """
        if start_isbn not in self.adj_list:
            return []

        visited: Set[str] = set()
        path: List[str] = []

        def _dfs(node: str, depth: int):
            if depth > max_depth or node in visited:
                return
            visited.add(node)
            path.append(node)

            # Sort edges by highest weight
            sorted_edges = sorted(self.adj_list.get(node, []), key=lambda e: e.weight, reverse=True)
            for edge in sorted_edges:
                if edge.target_isbn not in visited:
                    _dfs(edge.target_isbn, depth + 1)

        _dfs(start_isbn, 1)
        return [self.nodes_meta.get(isbn, {"isbn": isbn}) for isbn in path]

    def get_related_recommendations(self, isbn: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Returns highest affinity 1-hop and 2-hop neighbor books.
        """
        if isbn not in self.adj_list:
            return []

        scores: Dict[str, float] = {}

        # 1-hop neighbors
        for edge in self.adj_list.get(isbn, []):
            scores[edge.target_isbn] = scores.get(edge.target_isbn, 0.0) + edge.weight

            # 2-hop neighbors (damped)
            for sub_edge in self.adj_list.get(edge.target_isbn, []):
                if sub_edge.target_isbn != isbn:
                    scores[sub_edge.target_isbn] = scores.get(sub_edge.target_isbn, 0.0) + (sub_edge.weight * 0.4)

        # Exclude root node
        scores.pop(isbn, None)

        sorted_nodes = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        results = []
        for n_isbn, score in sorted_nodes:
            meta = self.nodes_meta.get(n_isbn, {"isbn": n_isbn, "title": f"Book {n_isbn}"})
            results.append({
                "isbn": n_isbn,
                "title": meta.get("title", ""),
                "category": meta.get("category", ""),
                "similarity_score": round(score, 3),
            })
        return results
