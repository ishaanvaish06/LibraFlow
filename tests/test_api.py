"""
Unit & Integration Tests for Phase 7: REST API Layer, OpenAPI & Security
"""
import pytest
from starlette.testclient import TestClient
from libflow.api.app import app


@pytest.fixture
def client():
    return TestClient(app)


def test_api_health_and_docs(client):
    res = client.get("/docs")
    assert res.status_code == 200


def test_user_registration_and_login_flow(client):
    # 1. Register Student
    reg_payload = {
        "user_id": "API-STU-01",
        "name": "Ishaan API",
        "email": "ishaan.api@test.com",
        "role": "STUDENT",
        "academic_year": 3,
        "major": "Computer Science",
    }
    reg_res = client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_res.status_code == 200
    assert reg_res.json()["user"]["user_id"] == "API-STU-01"

    # 2. Login
    login_res = client.post("/api/v1/auth/login", json={"user_id": "API-STU-01", "password": "any"})
    assert login_res.status_code == 200
    token_data = login_res.json()
    assert "access_token" in token_data
    token = token_data["access_token"]

    # 3. Profile Me
    headers = {"Authorization": f"Bearer {token}"}
    me_res = client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == 200
    assert me_res.json()["user_id"] == "API-STU-01"


def test_book_catalog_and_search_endpoints(client):
    # Register Book as Admin
    login_admin = client.post("/api/v1/auth/login", json={"user_id": "ADMIN-01", "password": "pwd"})
    admin_token = login_admin.json()["access_token"]
    headers = {"Authorization": f"Bearer {admin_token}"}

    book_payload = {
        "format_type": "PHYSICAL",
        "isbn": "978-0262033848",
        "title": "Introduction to Algorithms CLRS",
        "authors": ["Thomas H. Cormen", "Charles E. Leiserson"],
        "category": "Algorithms",
        "publication_year": 2009,
        "rating": 5.0,
        "keywords": ["DSA", "Graph", "Dynamic Programming"],
    }
    book_res = client.post("/api/v1/books", json=book_payload, headers=headers)
    assert book_res.status_code == 200

    # Add copy
    copy_res = client.post(
        "/api/v1/books/978-0262033848/copies",
        json={"copy_id": "CLRS-COPY-01", "branch_id": "BRANCH-DELHI"},
        headers=headers,
    )
    assert copy_res.status_code == 200

    # Autocomplete
    auto_res = client.get("/api/v1/books/autocomplete?prefix=Intro")
    assert auto_res.status_code == 200
    assert len(auto_res.json()["suggestions"]) >= 1

    # Search
    search_res = client.get("/api/v1/books/search?q=algorithms")
    assert search_res.status_code == 200
    assert search_res.json()["total_results"] >= 1


def test_smart_allocation_and_circulation_endpoints(client):
    # Request smart priority allocation
    alloc_res = client.post(
        "/api/v1/circulation/smart-allocation/request",
        json={"isbn": "978-0262033848", "user_id": "API-STU-01"},
    )
    assert alloc_res.status_code == 200
    assert "ENQUEUED" in alloc_res.json()["status"]

    # Issue book to user
    login_admin = client.post("/api/v1/auth/login", json={"user_id": "ADMIN-01", "password": "pwd"})
    headers = {"Authorization": f"Bearer {login_admin.json()['access_token']}"}

    issue_res = client.post(
        "/api/v1/circulation/issue",
        json={"copy_id": "CLRS-COPY-01", "user_id": "API-STU-01", "loan_days": 14},
        headers=headers,
    )
    assert issue_res.status_code == 200
    assert issue_res.json()["transaction"]["type"] == "BORROW"

    # Return book
    return_res = client.post(
        "/api/v1/circulation/return",
        json={"copy_id": "CLRS-COPY-01", "is_late": False, "is_damaged": False},
        headers=headers,
    )
    assert return_res.status_code == 200
    assert return_res.json()["result"]["status"] == "AVAILABLE"


def test_ai_intelligence_and_billing_endpoints(client):
    # Risk assessment
    risk_res = client.get("/api/v1/intelligence/risk-assessment/API-STU-01")
    assert risk_res.status_code == 200
    assert "risk_score_pct" in risk_res.json()["assessment"]

    # Recommendations
    recs_res = client.get("/api/v1/intelligence/recommendations/API-STU-01")
    assert recs_res.status_code == 200

    # Fine estimate & payment
    fine_est = client.get("/api/v1/billing/fine-estimate?isbn=978-0262033848&user_id=API-STU-01&overdue_days=2")
    assert fine_est.status_code == 200

    pay_res = client.post(
        "/api/v1/billing/pay",
        json={"user_id": "API-STU-01", "amount": 20.0, "payment_method": "UPI", "payment_metadata": {"vpa": "ishaan@upi"}},
    )
    assert pay_res.status_code == 200
    assert pay_res.json()["status"] == "SUCCESS"


def test_branches_and_cache_stats(client):
    branches_res = client.get("/api/v1/branches")
    assert branches_res.status_code == 200
    assert len(branches_res.json()["branches"]) == 3

    cache_res = client.get("/api/v1/system/cache-stats")
    assert cache_res.status_code == 200
    assert "hit_ratio_pct" in cache_res.json()["cache_stats"]
