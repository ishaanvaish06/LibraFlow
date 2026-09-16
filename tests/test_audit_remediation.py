"""
Tests for security, concurrency, outbox, and algorithmic audit remediations.
"""

from __future__ import annotations

from libflow.api.idempotency import IdempotencyStore
from libflow.core.passwords import hash_password, verify_password
from libflow.core.user import Student
from libflow.dsa.inverted_index import InvertedIndex
from libflow.dsa.priority_queue import SmartAllocationQueue
from libflow.dsa.trie import AutocompleteTrie


def test_password_hashing_generates_unique_salts():
    """Verify that identical plaintexts generate distinct hashes with fresh salts."""
    pwd = "SharedSecret123!"
    hash1 = hash_password(pwd)
    hash2 = hash_password(pwd)

    # Hashes MUST not be identical (different salts)
    assert hash1 != hash2

    # Both hashes must successfully verify
    assert verify_password(pwd, hash1) is True
    assert verify_password(pwd, hash2) is True
    assert verify_password("WrongSecret", hash1) is False


def test_idempotency_store_user_scoping():
    """Verify that different users with the same idempotency key do not collide."""
    store = IdempotencyStore()

    # User 1 claims key "req-1"
    ok1 = store.set_in_progress("req-1", user_id="USER-A")
    assert ok1 is True

    # User 2 claims the SAME key "req-1" - should succeed because it's namespaced
    ok2 = store.set_in_progress("req-1", user_id="USER-B")
    assert ok2 is True

    # User 1 retries key "req-1" - should fail (conflict)
    ok1_retry = store.set_in_progress("req-1", user_id="USER-A")
    assert ok1_retry is False

    # Complete User 1
    store.set_completed("req-1", 200, {"result": "user_a_done"}, user_id="USER-A")
    cached_a = store.get("req-1", user_id="USER-A")
    assert cached_a is not None
    assert cached_a["response_body"] == {"result": "user_a_done"}

    # User 2 has not completed yet
    cached_b = store.get("req-1", user_id="USER-B")
    assert cached_b is not None
    assert cached_b["status"] == "IN_PROGRESS"


def test_priority_queue_deterministic_fifo_tie_breaking():
    """Verify that requests with identical priority scores break ties strictly FIFO."""
    queue = SmartAllocationQueue(isbn="978-0132350884")

    # Create two students with identical academic parameters
    alice = Student(user_id="U-ALICE", name="Alice", email="alice@test.com", academic_year=3)
    bob = Student(user_id="U-BOB", name="Bob", email="bob@test.com", academic_year=3)

    # Both have the exact same custom priority
    req1 = queue.enqueue(request_id="REQ-1", user=alice, custom_priority=0.85)
    req2 = queue.enqueue(request_id="REQ-2", user=bob, custom_priority=0.85)

    assert req1.priority == req2.priority

    # Alice was enqueued first, so Alice MUST pop first
    popped1 = queue.pop_highest_priority()
    assert popped1 is not None
    assert popped1.user_id == "U-ALICE"
    assert popped1.request_id == "REQ-1"

    popped2 = queue.pop_highest_priority()
    assert popped2 is not None
    assert popped2.user_id == "U-BOB"
    assert popped2.request_id == "REQ-2"


def test_inverted_index_fast_removal_cleans_vocabulary():
    """Verify remove_book deletes indexed terms and cleans up empty entries."""
    from libflow.core.book import PhysicalBook

    index = InvertedIndex()
    book = PhysicalBook(
        isbn="ISBN-QUICK-TEST",
        title="Distributed Algorithmic Systems",
        authors=["Leslie Lamport"],
        category="Distributed Systems",
        publication_year=2024,
    )
    index.index_book(book)
    assert "lamport" in index.index
    assert "distributed" in index.index
    assert "ISBN-QUICK-TEST" in index.index["lamport"]

    # Remove book
    index.remove_book("ISBN-QUICK-TEST")

    # The empty set for 'lamport' must be purged from index
    assert "lamport" not in index.index
    assert "ISBN-QUICK-TEST" not in index.books


def test_trie_search_prefix_iterative_deduplication():
    """Verify Trie prefix search returns deduplicated, correctly ranked results."""
    trie = AutocompleteTrie()
    trie.insert("algorithm", "ID-1", "Introduction to Algorithms", weight=5.0)
    trie.insert("algebra", "ID-2", "Linear Algebra Done Right", weight=3.0)
    trie.insert("algo", "ID-1", "Introduction to Algorithms", weight=6.0)

    matches = trie.search_prefix("alg", limit=10)
    assert len(matches) == 2  # ID-1 deduplicated
    assert matches[0]["id"] == "ID-1"
    assert matches[0]["weight"] == 6.0
    assert matches[1]["id"] == "ID-2"
