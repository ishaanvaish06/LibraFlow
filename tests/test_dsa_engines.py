"""
Unit Tests for Phase 2: Advanced Data Structures & Algorithmic Engines
"""
from datetime import date, timedelta
from libflow.core.book import PhysicalBook
from libflow.core.user import Student
from libflow.dsa.trie import AutocompleteTrie
from libflow.dsa.inverted_index import InvertedIndex
from libflow.dsa.priority_queue import SmartAllocationQueue
from libflow.dsa.graph import BookGraphEngine


def test_trie_prefix_autocomplete():
    trie = AutocompleteTrie()
    trie.insert("Operating Systems", "ISBN-OS", "Operating Systems (Silberschatz)", weight=4.5)
    trie.insert("Operating System Concepts", "ISBN-OSC", "Operating System Concepts 10th", weight=4.8)
    trie.insert("Optimal Control", "ISBN-OC", "Optimal Control Theory", weight=3.2)
    trie.insert("Database Internals", "ISBN-DB", "Database Internals", weight=4.9)

    results = trie.search_prefix("oper")
    assert len(results) == 2
    # Highest weight first
    assert results[0]["id"] == "ISBN-OSC"
    assert results[1]["id"] == "ISBN-OS"

    assert len(trie.search_prefix("data")) == 1
    assert len(trie.search_prefix("xyz")) == 0


def test_inverted_index_multi_criteria_search():
    index = InvertedIndex()

    book1 = PhysicalBook(
        isbn="ISBN-1",
        title="Introduction to Algorithms CLRS",
        authors=["Thomas Cormen", "Charles Leiserson"],
        category="Computer Science",
        publication_year=2009,
        description="Comprehensive textbook on data structures and algorithms.",
        keywords=["DSA", "Trees", "Sorting"],
        rating=4.9,
    )
    book2 = PhysicalBook(
        isbn="ISBN-2",
        title="Designing Data-Intensive Applications",
        authors=["Martin Kleppmann"],
        category="Distributed Systems",
        publication_year=2017,
        description="Reliable, scalable, and maintainable systems guide.",
        keywords=["Databases", "Distributed", "Consensus"],
        rating=5.0,
    )

    index.index_book(book1)
    index.index_book(book2)

    # Keyword search
    res = index.search("algorithms")
    assert len(res) >= 1
    assert res[0]["book"].isbn == "ISBN-1"

    # Search author
    res_author = index.search("Kleppmann")
    assert len(res_author) == 1
    assert res_author[0]["book"].isbn == "ISBN-2"

    # Category filter
    res_cat = index.search("systems", category="Distributed Systems")
    assert len(res_cat) == 1
    assert res_cat[0]["book"].isbn == "ISBN-2"


def test_smart_allocation_priority_queue():
    # Student A: 3rd year, exam tomorrow (high urgency)
    student_a = Student(
        user_id="STU-A",
        name="Ishaan (3rd Yr CS, Exam Tomorrow)",
        email="ishaan@test.com",
        academic_year=3,
        exam_date=date.today() + timedelta(days=1),
    )

    # Student B: 1st year, exam in 20 days
    student_b = Student(
        user_id="STU-B",
        name="Junior (1st Yr)",
        email="junior@test.com",
        academic_year=1,
        exam_date=date.today() + timedelta(days=20),
    )

    p_a = SmartAllocationQueue.calculate_priority(student_a)
    p_b = SmartAllocationQueue.calculate_priority(student_b)

    assert p_a > p_b  # Student A must have higher priority

    queue = SmartAllocationQueue(isbn="ISBN-OS")
    queue.enqueue("REQ-1", student_b)  # Enqueued first
    queue.enqueue("REQ-2", student_a)  # Enqueued second

    # Student A should be popped FIRST despite enqueuing second!
    popped = queue.pop_highest_priority()
    assert popped is not None
    assert popped.user_id == "STU-A"

    popped_second = queue.pop_highest_priority()
    assert popped_second is not None
    assert popped_second.user_id == "STU-B"


def test_graph_book_relations_and_traversal():
    graph = BookGraphEngine()

    graph.add_book_node("B-DSA", "Data Structures", "CS")
    graph.add_book_node("B-ALGO", "Algorithms", "CS")
    graph.add_book_node("B-CPP", "Modern C++", "Programming")
    graph.add_book_node("B-CP", "Competitive Programming", "Algorithms")

    # Construct relationship hierarchy
    graph.add_relation("B-DSA", "B-ALGO", weight=0.9, relation_type="PREREQUISITE_FOR")
    graph.add_relation("B-DSA", "B-CPP", weight=0.7, relation_type="SIMILAR_TO")
    graph.add_relation("B-ALGO", "B-CP", weight=0.95, relation_type="PREREQUISITE_FOR")

    # BFS shortest path from DSA to Competitive Programming
    path = graph.bfs_shortest_path("B-DSA", "B-CP")
    assert path is not None
    assert len(path) == 3
    assert [p["isbn"] for p in path] == ["B-DSA", "B-ALGO", "B-CP"]

    # Graph neighbor recommendations for DSA
    recs = graph.get_related_recommendations("B-DSA", top_k=3)
    assert len(recs) >= 2
    rec_isbns = [r["isbn"] for r in recs]
    assert "B-ALGO" in rec_isbns
