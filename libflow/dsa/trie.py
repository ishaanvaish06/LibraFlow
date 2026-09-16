"""
Trie (Prefix Tree) Implementation for Real-Time Autocomplete
O(K) lookup where K is the query prefix length.
"""
from typing import Dict, List, Tuple, Any


class TrieNode:
    def __init__(self):
        self.children: Dict[str, TrieNode] = {}
        self.is_end_of_word: bool = False
        # Store associated payloads: (item_id, display_text, weight/popularity)
        self.payloads: List[Tuple[str, str, float]] = []


class AutocompleteTrie:
    """
    In-memory Trie supporting case-insensitive prefix matching and weighted autocomplete ranking.
    """

    def __init__(self):
        self.root = TrieNode()
        self._total_entries = 0

    def insert(self, phrase: str, item_id: str, display_text: str, weight: float = 1.0) -> None:
        """
        Inserts a searchable phrase into the Trie linked to an item (e.g. Book ISBN or Title).
        """
        if not phrase or not phrase.strip():
            return

        normalized = phrase.strip().lower()
        node = self.root

        for char in normalized:
            if char not in node.children:
                node.children[char] = TrieNode()
            node = node.children[char]

        node.is_end_of_word = True
        # Check if already present to update weight or avoid duplicate
        for i, (existing_id, disp, w) in enumerate(node.payloads):
            if existing_id == item_id:
                node.payloads[i] = (item_id, display_text, max(w, weight))
                return

        node.payloads.append((item_id, display_text, weight))
        self._total_entries += 1

    def search_prefix(self, prefix: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Finds all items matching the prefix, sorted by highest weight.
        Uses iterative stack traversal to prevent recursion depth exhaustion and
        deduplicates during traversal to minimize sorting overhead.
        """
        if not prefix:
            return []

        normalized = prefix.strip().lower()
        node = self.root

        for char in normalized:
            if char not in node.children:
                return []
            node = node.children[char]

        # item_id -> (display_text, weight)
        best_items: Dict[str, Tuple[str, float]] = {}
        stack = [node]

        while stack:
            curr = stack.pop()
            if curr.is_end_of_word:
                for item_id, display_text, weight in curr.payloads:
                    if item_id not in best_items or weight > best_items[item_id][1]:
                        best_items[item_id] = (display_text, weight)
            for child in curr.children.values():
                stack.append(child)

        # Sort only deduplicated candidates by (-weight, display_text)
        sorted_items = sorted(
            best_items.items(),
            key=lambda item: (-item[1][1], item[1][0]),
        )

        return [
            {"id": item_id, "text": disp, "weight": weight}
            for item_id, (disp, weight) in sorted_items[:limit]
        ]

    def size(self) -> int:
        return self._total_entries
