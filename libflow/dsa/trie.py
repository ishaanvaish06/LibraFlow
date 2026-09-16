"""
Trie (Prefix Tree) Implementation for Real-Time Autocomplete
O(K) lookup where K is the query prefix length.
"""
from typing import Dict, List, Set, Tuple, Any


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
        """
        if not prefix:
            return []

        normalized = prefix.strip().lower()
        node = self.root

        for char in normalized:
            if char not in node.children:
                return []
            node = node.children[char]

        results: List[Tuple[str, str, float]] = []
        self._collect_all(node, results)

        # Sort by weight descending, then by display text
        results.sort(key=lambda x: (-x[2], x[1]))

        # Deduplicate while preserving rank order
        seen: Set[str] = set()
        deduped: List[Dict[str, Any]] = []
        for item_id, display_text, weight in results:
            if item_id not in seen:
                seen.add(item_id)
                deduped.append({
                    "id": item_id,
                    "text": display_text,
                    "weight": weight,
                })
                if len(deduped) >= limit:
                    break

        return deduped

    def _collect_all(self, node: TrieNode, results: List[Tuple[str, str, float]]) -> None:
        if node.is_end_of_word:
            results.extend(node.payloads)

        for child in node.children.values():
            self._collect_all(child, results)

    def size(self) -> int:
        return self._total_entries
