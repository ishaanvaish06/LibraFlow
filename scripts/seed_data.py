"""
Seed the library with real-world textbooks, branches, users, and a graph.

Usage:
    LIBRAFLOW_STORAGE=memory  python scripts/seed_data.py   # in-memory demo
    LIBRAFLOW_STORAGE=postgres python scripts/seed_data.py  # needs Postgres+Redis up

Prerequisite for the Postgres backend: ``alembic upgrade head`` must have
run so the schema exists.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from libflow.api.dependencies import build_container
from libflow.seed import seed_library

if __name__ == "__main__":
    container = build_container()
    try:
        seed_library(container)
        print(
            f"[SUCCESS] LibraFlow seeded "
            f"[backend={container.storage_backend}] "
            f"({len(container.book_repo.list_books())} books, "
            f"{len(container.user_repo.list_users())} users, "
            f"{len(container.branch_repo.list_branches())} branches)."
        )
    finally:
        container.dispose()