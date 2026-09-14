"""
Locust load-test definitions for LibraFlow.

Run against a running server (seeded in-memory container or Postgres):

    locust -f benchmarks/load_test.py --host http://127.0.0.1:8000 --headless \
           -u 50 -r 10 --run-time 30s

The on_start handler authenticates as ADMIN-01 so tasks that require a
permission token succeed.  Public search runs without a token.
"""

from __future__ import annotations

import random

from locust import HttpUser, between, task


ISBN_POOL = [
    "978-0132350884",
    "978-0262033848",
    "978-1491950357",
    "978-1492040347",
    "978-1118063330",
    "978-0134494166",
]

QUERY_POOL = ["algorithm", "python", "distributed", "database", "clean", "concurrency"]


class LibraFlowUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self) -> None:
        resp = self.client.post(
            "/api/v1/auth/login",
            json={"user_id": "ADMIN-01", "password": "admin123"},
        )
        if resp.status_code == 200:
            token = resp.json()["access_token"]
            self.client.headers["Authorization"] = f"Bearer {token}"
        else:
            # If server isn't seeded, tasks will get 401s (still valid for
            # load measuring).
            pass

    @task(5)
    def search_public(self) -> None:
        self.client.get(
            "/api/v1/books/public/search",
            params={"q": random.choice(QUERY_POOL)},
        )

    @task(3)
    def get_catalog_book(self) -> None:
        isbn = random.choice(ISBN_POOL)
        self.client.get(f"/api/v1/books/{isbn}")

    @task(2)
    def get_recommendations(self) -> None:
        isbn = random.choice(ISBN_POOL)
        self.client.get(
            f"/api/v1/intelligence/recommendations/STU-ALICE",
            params={"top_k": 3},
        )

    @task(1)
    def get_learning_path(self) -> None:
        isbn = random.choice(ISBN_POOL)
        self.client.get(f"/api/v1/intelligence/learning-path/{isbn}")

    @task(1)
    def system_stats(self) -> None:
        self.client.get("/api/v1/system/notifications/ADMIN-01")

    @task(1)
    def smart_allocation(self) -> None:
        isbn = random.choice(ISBN_POOL)
        self.client.post(
            "/api/v1/circulation/smart-allocation/request",
            json={"isbn": isbn, "user_id": "STU-ALICE"},
        )