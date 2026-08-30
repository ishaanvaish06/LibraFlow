"""
Seed Data Script for LibraFlow
Populates realistic books, branches, users, graph edges, and inventory copies.
"""
import sys
import os

# Add root directory to python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from datetime import date, timedelta
from typing import Tuple

from libflow.core.enums import BookFormat, UserRole
from libflow.core.branch import LibraryBranch
from libflow.core.factory import BookFactory, UserFactory
from libflow.storage.database import LibraryDatabase
from libflow.dsa.trie import AutocompleteTrie
from libflow.dsa.inverted_index import InvertedIndex
from libflow.dsa.graph import BookGraphEngine
from libflow.storage.cache import DistributedCache
from libflow.patterns.reservation_queue import BookReservationQueueManager
from libflow.patterns.observer_notification import NotificationDispatcher
from libflow.ai.recommendation_engine import AIRecommendationEngine
from libflow.ai.demand_forecaster import DemandForecaster
from libflow.distributed.branch_manager import MultiBranchManager
from libflow.services import CatalogService, CirculationService, BillingService, IntelligenceService


def build_and_seed_libraflow_ecosystem() -> Tuple[
    CatalogService, CirculationService, BillingService, IntelligenceService, MultiBranchManager
]:
    # 1. Core Infrastructure
    db = LibraryDatabase()
    cache = DistributedCache(capacity=5000)
    trie = AutocompleteTrie()
    index = InvertedIndex()
    graph = BookGraphEngine()
    dispatcher = NotificationDispatcher()
    reservation_mgr = BookReservationQueueManager(notification_dispatcher=dispatcher)
    forecaster = DemandForecaster()
    recommender = AIRecommendationEngine(graph_engine=graph)
    branch_mgr = MultiBranchManager()

    # 2. Instantiate Orchestration Services
    from libflow.storage.lock_manager import ConcurrencyLockManager
    lock_mgr = ConcurrencyLockManager()

    catalog_svc = CatalogService(db, trie, index, cache)
    circulation_svc = CirculationService(db, lock_mgr, cache, reservation_mgr, dispatcher, forecaster)
    billing_svc = BillingService(db, reservation_mgr, dispatcher)
    intelligence_svc = IntelligenceService(db, recommender, graph, forecaster)

    # 3. Seed Branches
    branches = [
        LibraryBranch("BRANCH-DELHI", "Delhi Main Campus Library", "Delhi", "Connaught Place, New Delhi"),
        LibraryBranch("BRANCH-MUMBAI", "Mumbai Tech & Engineering Wing", "Mumbai", "Powai, Mumbai"),
        LibraryBranch("BRANCH-PUNE", "Pune Research Library", "Pune", "Shivaji Nagar, Pune"),
    ]
    for b in branches:
        db.save_branch(b)
        branch_mgr.register_branch(b)

    # 4. Seed Users
    users_data = [
        ("STUDENT", "STU-ISHAAN", "Ishaan", "ishaan@example.com", {"academic_year": 3, "exam_date": date.today() + timedelta(days=1), "major": "Computer Science"}),
        ("STUDENT", "STU-ALICE", "Alice", "alice@example.com", {"academic_year": 1, "exam_date": date.today() + timedelta(days=25), "major": "Electrical Engineering"}),
        ("STUDENT", "STU-BOB", "Bob", "bob@example.com", {"academic_year": 4, "exam_date": date.today() + timedelta(days=3), "major": "Computer Science"}),
        ("STUDENT", "STU-RAHUL", "Rahul (Risky)", "rahul@example.com", {"academic_year": 2, "exam_date": date.today() + timedelta(days=15), "major": "Mechanical"}),
        ("FACULTY", "FAC-DR-SHARMA", "Dr. Sharma", "sharma@univ.edu", {"department": "Computer Science & Engineering"}),
        ("LIBRARIAN", "LIB-SARAH", "Sarah Jenkins", "sarah@library.org", {"staff_code": "LIB-001"}),
        ("ADMIN", "ADM-SYSTEM", "Root Admin", "admin@libraflow.org", {}),
    ]

    for role, uid, name, email, extra in users_data:
        u = UserFactory.create_user(role=role, user_id=uid, name=name, email=email, **extra)
        db.save_user(u)

    # Seed Rahul's risky history
    rahul = db.get_user("STU-RAHUL")
    if rahul:
        for i in range(5):
            rahul.add_borrow(f"OLD-COPY-{i}", f"OLD-ISBN-{i}")
            rahul.record_return(f"OLD-COPY-{i}", is_late=True, is_damaged=(i == 0))
        rahul.add_fine(120.0)

    # 5. Seed Real-World Computer Science & Engineering Catalog
    books_catalog = [
        {
            "format": "PHYSICAL",
            "isbn": "978-0132350884",
            "title": "Clean Code: A Handbook of Agile Software Craftsmanship",
            "authors": ["Robert C. Martin"],
            "category": "Software Engineering",
            "year": 2008,
            "rating": 4.9,
            "difficulty": "Intermediate",
            "keywords": ["Refactoring", "Clean Architecture", "OOP", "Design Patterns"],
            "description": "Even bad code can function. But if code isn't clean, it can bring a development organization to its knees.",
            "copies": [("CC-DEL-01", "BRANCH-DELHI", "A1-01"), ("CC-DEL-02", "BRANCH-DELHI", "A1-02"), ("CC-MUM-01", "BRANCH-MUMBAI", "B2-05")],
        },
        {
            "format": "PHYSICAL",
            "isbn": "978-0262033848",
            "title": "Introduction to Algorithms (CLRS 3rd Edition)",
            "authors": ["Thomas H. Cormen", "Charles E. Leiserson", "Ronald L. Rivest", "Clifford Stein"],
            "category": "Data Structures & Algorithms",
            "year": 2009,
            "rating": 5.0,
            "difficulty": "Advanced",
            "keywords": ["DSA", "Dynamic Programming", "Graph Theory", "Greedy", "Heaps"],
            "description": "Comprehensive textbook covering modern algorithms, rigorous proofs, and asymptotic complexities.",
            "copies": [("CLRS-DEL-01", "BRANCH-DELHI", "A2-10"), ("CLRS-MUM-01", "BRANCH-MUMBAI", "C1-02")],
        },
        {
            "format": "PHYSICAL",
            "isbn": "978-1491950357",
            "title": "Designing Data-Intensive Applications",
            "authors": ["Martin Kleppmann"],
            "category": "Distributed Systems",
            "year": 2017,
            "rating": 5.0,
            "difficulty": "Advanced",
            "keywords": ["Databases", "Distributed Consensus", "Replication", "Partitioning", "Transactions"],
            "description": "The definitive guide to the architecture, internals, and tradeoffs of modern distributed data systems.",
            "copies": [("DDIA-DEL-01", "BRANCH-DELHI", "B1-04"), ("DDIA-PUN-01", "BRANCH-PUNE", "A3-01")],
        },
        {
            "format": "PHYSICAL",
            "isbn": "978-1492040347",
            "title": "Database Internals: A Deep Dive into Storage Engines",
            "authors": ["Alex Petrov"],
            "category": "Distributed Systems",
            "year": 2019,
            "rating": 4.8,
            "difficulty": "Advanced",
            "keywords": ["B-Trees", "LSM-Trees", "Storage Engines", "Transactions", "WAL"],
            "description": "Examines storage engines, distributed consensus protocols, and consensus algorithms like Paxos and Raft.",
            "copies": [("DBI-DEL-01", "BRANCH-DELHI", "B1-05")],
        },
        {
            "format": "PHYSICAL",
            "isbn": "978-1118063330",
            "title": "Operating System Concepts (10th Edition)",
            "authors": ["Abraham Silberschatz", "Peter B. Galvin", "Greg Gagne"],
            "category": "Computer Systems",
            "year": 2018,
            "rating": 4.7,
            "difficulty": "Intermediate",
            "keywords": ["Kernel", "Virtual Memory", "Deadlocks", "Processes", "Concurrency"],
            "description": "Fundamental textbook covering OS architecture, CPU scheduling, memory management, and file systems.",
            "copies": [("OSC-DEL-01", "BRANCH-DELHI", "A3-01")],
        },
        {
            "format": "PHYSICAL",
            "isbn": "978-0134494166",
            "title": "Clean Architecture: A Craftsman's Guide to Software Structure",
            "authors": ["Robert C. Martin"],
            "category": "Software Engineering",
            "year": 2017,
            "rating": 4.8,
            "difficulty": "Intermediate",
            "keywords": ["Architecture", "SOLID", "Microservices", "Design Patterns"],
            "description": "Universal rules of software architecture, dependency inversion, component principles, and boundary decoupling.",
            "copies": [("CA-DEL-01", "BRANCH-DELHI", "A1-03")],
        },
        {
            "format": "EBOOK",
            "isbn": "978-0134685991",
            "title": "Effective Java (3rd Edition) Digital Edition",
            "authors": ["Joshua Bloch"],
            "category": "Programming Languages",
            "year": 2018,
            "rating": 4.9,
            "difficulty": "Advanced",
            "keywords": ["Java", "OOP", "Generics", "Concurrency", "Design Patterns"],
            "description": "Best practices for the Java platform covering lambdas, streams, generics, and concurrent programming.",
            "download_url": "https://cdn.libraflow.org/ebooks/effective_java_3e.pdf",
            "file_size_mb": 9.2,
        },
        {
            "format": "EBOOK",
            "isbn": "978-1492051725",
            "title": "Fluent Python: Clear, Concise, and Effective Programming",
            "authors": ["Luciano Ramalho"],
            "category": "Programming Languages",
            "year": 2022,
            "rating": 4.9,
            "difficulty": "Intermediate",
            "keywords": ["Python", "AsyncIO", "Metaprogramming", "Data Structures"],
            "description": "Deep dive into Python language features, generators, coroutines, and type annotations.",
            "download_url": "https://cdn.libraflow.org/ebooks/fluent_python_2e.pdf",
            "file_size_mb": 14.8,
        },
    ]

    for b_data in books_catalog:
        book = catalog_svc.register_book(
            format_type=b_data["format"],
            actor_id="ADM-SYSTEM",
            isbn=b_data["isbn"],
            title=b_data["title"],
            authors=b_data["authors"],
            category=b_data["category"],
            publication_year=b_data["year"],
            rating=b_data["rating"],
            difficulty_level=b_data["difficulty"],
            keywords=b_data["keywords"],
            description=b_data["description"],
            download_url=b_data.get("download_url"),
            file_size_mb=b_data.get("file_size_mb"),
        )
        recommender.register_book(book)

        if "copies" in b_data:
            for cid, branch, shelf in b_data["copies"]:
                catalog_svc.add_physical_copy(
                    isbn=b_data["isbn"],
                    copy_id=cid,
                    branch_id=branch,
                    shelf_location=shelf,
                    actor_id="ADM-SYSTEM",
                )

    # 6. Build Relationship Graph
    graph.add_relation("978-0262033848", "978-1491950357", weight=0.85, relation_type="PREREQUISITE_FOR")  # CLRS -> DDIA
    graph.add_relation("978-1118063330", "978-1491950357", weight=0.90, relation_type="PREREQUISITE_FOR")  # OS -> DDIA
    graph.add_relation("978-1491950357", "978-1492040347", weight=0.95, relation_type="SIMILAR_TO")        # DDIA -> DB Internals
    graph.add_relation("978-0132350884", "978-0134494166", weight=0.95, relation_type="PREREQUISITE_FOR")  # Clean Code -> Clean Architecture
    graph.add_relation("978-0134685991", "978-0132350884", weight=0.80, relation_type="SIMILAR_TO")        # Effective Java -> Clean Code

    return catalog_svc, circulation_svc, billing_svc, intelligence_svc, branch_mgr


if __name__ == "__main__":
    cat, circ, bill, intel, branch = build_and_seed_libraflow_ecosystem()
    print("[SUCCESS] LibraFlow ecosystem seeded with 8 textbooks, 3 branches, 7 users, and graph relations.")
