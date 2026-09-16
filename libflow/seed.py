"""
Library seeding — idempotent-ish seed used by scripts, tests, and the
containers' entrypoint.

Works against any assembled container (in-memory or Postgres) via repository
interfaces, so the app never needs a second-class setup path.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING, Any, Dict, List

from libflow.core.branch import LibraryBranch
from libflow.core.factory import UserFactory

if TYPE_CHECKING:
    from libflow.api.dependencies import LibraFlowContainer

BRANCHES = [
    LibraryBranch("BRANCH-DELHI", "Delhi Main Campus Library", "Delhi", "Connaught Place, New Delhi"),
    LibraryBranch("BRANCH-MUMBAI", "Mumbai Tech & Engineering Wing", "Mumbai", "Powai, Mumbai"),
    LibraryBranch("BRANCH-PUNE", "Pune Research Library", "Pune", "Shivaji Nagar, Pune"),
]

USERS: List[Dict[str, Any]] = [
    {"role": "STUDENT", "user_id": "STU-ISHAAN", "name": "Ishaan", "email": "ishaan@example.com",
     "academic_year": 3, "major": "Computer Science", "exam_date": date.today() + timedelta(days=1)},
    {"role": "STUDENT", "user_id": "STU-ALICE", "name": "Alice", "email": "alice@example.com",
     "academic_year": 1, "major": "Electrical Engineering", "exam_date": date.today() + timedelta(days=25)},
    {"role": "STUDENT", "user_id": "STU-BOB", "name": "Bob", "email": "bob@example.com",
     "academic_year": 4, "major": "Computer Science", "exam_date": date.today() + timedelta(days=3)},
    {"role": "STUDENT", "user_id": "STU-RAHUL", "name": "Rahul (Risky)", "email": "rahul@example.com",
     "academic_year": 2, "major": "Mechanical", "exam_date": date.today() + timedelta(days=15)},
    {"role": "FACULTY", "user_id": "FAC-DR-SHARMA", "name": "Dr. Sharma", "email": "sharma@univ.edu",
     "department": "Computer Science & Engineering"},
    {"role": "LIBRARIAN", "user_id": "LIB-SARAH", "name": "Sarah Jenkins", "email": "sarah@library.org",
     "staff_code": "LIB-001"},
    {"role": "ADMIN", "user_id": "ADMIN-01", "name": "Root Admin", "email": "admin@libraflow.org"},
]

DEFAULT_ADMIN_ID_PASSWORD = ("ADMIN-01", "admin123")
USER_PASSWORD = "passw0rd"

BOOKS: List[Dict[str, Any]] = [
    {
        "format": "PHYSICAL", "isbn": "978-0132350884",
        "title": "Clean Code: A Handbook of Agile Software Craftsmanship",
        "authors": ["Robert C. Martin"], "category": "Software Engineering", "year": 2008,
        "rating": 4.9, "difficulty": "Intermediate",
        "keywords": ["Refactoring", "Clean Architecture", "OOP", "Design Patterns"],
        "description": "Even bad code can function. But if code isn't clean, it can bring a development organization to its knees.",
        "copies": [("CC-DEL-01", "BRANCH-DELHI", "A1-01"), ("CC-DEL-02", "BRANCH-DELHI", "A1-02"),
                   ("CC-MUM-01", "BRANCH-MUMBAI", "B2-05")],
    },
    {
        "format": "PHYSICAL", "isbn": "978-0262033848",
        "title": "Introduction to Algorithms (CLRS 3rd Edition)",
        "authors": ["Thomas H. Cormen", "Charles E. Leiserson", "Ronald L. Rivest", "Clifford Stein"],
        "category": "Data Structures & Algorithms", "year": 2009, "rating": 5.0, "difficulty": "Advanced",
        "keywords": ["DSA", "Dynamic Programming", "Graph Theory", "Greedy", "Heaps"],
        "description": "Comprehensive textbook covering modern algorithms, rigorous proofs, and asymptotic complexities.",
        "copies": [("CLRS-DEL-01", "BRANCH-DELHI", "A2-10"), ("CLRS-MUM-01", "BRANCH-MUMBAI", "C1-02")],
    },
    {
        "format": "PHYSICAL", "isbn": "978-1491950357",
        "title": "Designing Data-Intensive Applications",
        "authors": ["Martin Kleppmann"], "category": "Distributed Systems", "year": 2017,
        "rating": 5.0, "difficulty": "Advanced",
        "keywords": ["Databases", "Distributed Consensus", "Replication", "Partitioning", "Transactions"],
        "description": "The definitive guide to the architecture, internals, and tradeoffs of modern distributed data systems.",
        "copies": [("DDIA-DEL-01", "BRANCH-DELHI", "B1-04"), ("DDIA-PUN-01", "BRANCH-PUNE", "A3-01")],
    },
    {
        "format": "PHYSICAL", "isbn": "978-1492040347",
        "title": "Database Internals: A Deep Dive into Storage Engines",
        "authors": ["Alex Petrov"], "category": "Distributed Systems", "year": 2019,
        "rating": 4.8, "difficulty": "Advanced",
        "keywords": ["B-Trees", "LSM-Trees", "Storage Engines", "Transactions", "WAL"],
        "description": "Examines storage engines, distributed consensus protocols, and consensus algorithms like Paxos and Raft.",
        "copies": [("DBI-DEL-01", "BRANCH-DELHI", "B1-05")],
    },
    {
        "format": "PHYSICAL", "isbn": "978-1118063330",
        "title": "Operating System Concepts (10th Edition)",
        "authors": ["Abraham Silberschatz", "Peter B. Galvin", "Greg Gagne"],
        "category": "Computer Systems", "year": 2018, "rating": 4.7, "difficulty": "Intermediate",
        "keywords": ["Kernel", "Virtual Memory", "Deadlocks", "Processes", "Concurrency"],
        "description": "Fundamental textbook covering OS architecture, CPU scheduling, memory management, and file systems.",
        "copies": [("OSC-DEL-01", "BRANCH-DELHI", "A3-01")],
    },
    {
        "format": "PHYSICAL", "isbn": "978-0134494166",
        "title": "Clean Architecture: A Craftsman's Guide to Software Structure",
        "authors": ["Robert C. Martin"], "category": "Software Engineering", "year": 2017,
        "rating": 4.8, "difficulty": "Intermediate",
        "keywords": ["Architecture", "SOLID", "Microservices", "Design Patterns"],
        "description": "Universal rules of software architecture, dependency inversion, component principles, and boundary decoupling.",
        "copies": [("CA-DEL-01", "BRANCH-DELHI", "A1-03")],
    },
    {
        "format": "EBOOK", "isbn": "978-0134685991",
        "title": "Effective Java (3rd Edition) Digital Edition",
        "authors": ["Joshua Bloch"], "category": "Programming Languages", "year": 2018,
        "rating": 4.9, "difficulty": "Advanced",
        "keywords": ["Java", "OOP", "Generics", "Concurrency", "Design Patterns"],
        "description": "Best practices for the Java platform covering lambdas, streams, generics, and concurrent programming.",
        "download_url": "https://cdn.libraflow.org/ebooks/effective_java_3e.pdf", "file_size_mb": 9.2,
    },
    {
        "format": "EBOOK", "isbn": "978-1492051725",
        "title": "Fluent Python: Clear, Concise, and Effective Programming",
        "authors": ["Luciano Ramalho"], "category": "Programming Languages", "year": 2022,
        "rating": 4.9, "difficulty": "Intermediate",
        "keywords": ["Python", "AsyncIO", "Metaprogramming", "Data Structures"],
        "description": "Deep dive into Python language features, generators, coroutines, and type annotations.",
        "download_url": "https://cdn.libraflow.org/ebooks/fluent_python_2e.pdf", "file_size_mb": 14.8,
    },
]

GRAPH_RELATIONS = [
    ("978-0262033848", "978-1491950357", 0.85, "PREREQUISITE_FOR"),
    ("978-1118063330", "978-1491950357", 0.90, "PREREQUISITE_FOR"),
    ("978-1491950357", "978-1492040347", 0.95, "SIMILAR_TO"),
    ("978-0132350884", "978-0134494166", 0.95, "PREREQUISITE_FOR"),
    ("978-0134685991", "978-0132350884", 0.80, "SIMILAR_TO"),
]


def seed_library(container: "LibraFlowContainer") -> None:
    # 1. Branches
    for branch in BRANCHES:
        container.branch_repo.save_branch(branch)
        container.branch_mgr.register_branch(branch)

    # 2. Users (the ADMIN-01 default password is used by local demos/tests)
    for u_data in USERS:
        role = u_data["role"]
        user = UserFactory.create_user(
            role=role,
            user_id=u_data["user_id"],
            name=u_data["name"],
            email=u_data["email"],
            password=DEFAULT_ADMIN_ID_PASSWORD[1] if role == "ADMIN" and u_data["user_id"] == "ADMIN-01" else USER_PASSWORD,
            branch_id="BRANCH-DELHI" if role != "LIBRARIAN" else "BRANCH-MUMBAI",
            **{k: v for k, v in u_data.items() if k not in ("role", "user_id", "name", "email")},
        )
        container.user_repo.save_user(user)

    # Rahul's deliberately poor track record — drives a HIGH risk score.
    rahul = container.user_repo.get_user("STU-RAHUL")
    if rahul:
        for i in range(5):
            rahul.add_borrow(f"OLD-COPY-{i}", f"OLD-ISBN-{i}")
            rahul.record_return(f"OLD-COPY-{i}", is_late=True, is_damaged=(i == 0))
        rahul.add_fine(120.0)
        container.user_repo.save_user(rahul)

    # 3. Catalog + copies
    for b_data in BOOKS:
        book = container.catalog_svc.register_book(
            format_type=b_data["format"],
            actor_id="ADMIN-01",
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
        container.recommender.register_book(book)
        for cid, branch, shelf in b_data.get("copies", []):
            container.catalog_svc.add_physical_copy(
                isbn=b_data["isbn"],
                copy_id=cid,
                branch_id=branch,
                shelf_location=shelf,
                actor_id="ADMIN-01",
            )

    # 4. Relationship graph
    for src, dst, weight, rel_type in GRAPH_RELATIONS:
        container.graph.add_relation(src, dst, weight=weight, relation_type=rel_type)

    # 5. A little circulation + interaction history so recommendations,
    #    demand forecasts, and the risk model have realistic inputs.
    interactions = [
        ("STU-ISHAAN", "978-0132350884", 4.5),
        ("STU-ISHAAN", "978-0262033848", 5.0),
        ("STU-BOB", "978-0132350884", 5.0),
        ("STU-BOB", "978-0134494166", 4.0),
        ("FAC-DR-SHARMA", "978-1491950357", 5.0),
        ("FAC-DR-SHARMA", "978-1492040347", 4.5),
    ]
    for uid, isbn, rating in interactions:
        container.recommender.record_user_interaction(uid, isbn, rating)

    # Returned-on-time loans build clean history for the risk model.
    clean_user = container.user_repo.get_user("STU-ALICE")
    for isbn, copies in [("978-0132350884", ["CC-DEL-01"]), ("978-1118063330", ["OSC-DEL-01"])]:
        for cid in copies:
            container.circulation_svc.issue_physical_book(cid, clean_user.user_id if clean_user else "STU-BOB", actor_id="LIB-SARAH")
            if clean_user:
                container.circulation_svc.return_physical_book(cid, actor_id="LIB-SARAH", is_late=False, is_damaged=False)
