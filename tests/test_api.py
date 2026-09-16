"""
API integration tests: auth, catalog, circulation, intelligence, billing,
branches, and system routes over the real FastAPI app with an in-memory
container.
"""

from __future__ import annotations


from tests.conftest import auth_headers


def test_api_health_and_docs(client):
    assert client.get("/docs").status_code == 200
    assert client.get("/").json()["service"] == "LibraFlow"


def test_registration_login_password_rejection(client):
    # Register
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "user_id": "STU-API-TEST",
            "name": "API Test Student",
            "email": "api.test@example.com",
            "password": "s3cret-pass",
            "role": "STUDENT",
        },
    )
    assert reg.status_code == 200
    assert reg.json()["user"]["user_id"] == "STU-API-TEST"

    # Wrong password rejected with 401 (DoD 1.6)
    bad = client.post("/api/v1/auth/login", json={"user_id": "STU-API-TEST", "password": "nope"})
    assert bad.status_code == 401

    # Correct password logs in
    ok = client.post("/api/v1/auth/login", json={"user_id": "STU-API-TEST", "password": "s3cret-pass"})
    assert ok.status_code == 200
    token = ok.json()["access_token"]

    # /me returns the profile
    me = client.get("/api/v1/auth/me", headers=auth_headers(token))
    assert me.status_code == 200
    assert me.json()["user_id"] == "STU-API-TEST"

    # Duplicate registration rejected
    dup = client.post(
        "/api/v1/auth/register",
        json={
            "user_id": "STU-API-TEST",
            "name": "Dup",
            "email": "x@x.com",
            "password": "whatever",
        },
    )
    assert dup.status_code == 409


def test_default_admin_seed_login(client):
    login = client.post("/api/v1/auth/login", json={"user_id": "ADMIN-01", "password": "admin123"})
    assert login.status_code == 200
    assert login.json()["role"] == "ADMIN"


def test_protected_routes_require_auth(client):
    # No token -> 401
    assert client.get("/api/v1/books/search").status_code == 401
    assert client.get("/api/v1/books/autocomplete?prefix=a").status_code == 401
    assert client.get("/api/v1/books/978-0132350884").status_code == 401
    assert client.get("/api/v1/intelligence/recommendations/STU-ALICE").status_code == 401
    assert client.get("/api/v1/system/cache-stats").status_code == 401

    # Public search is explicitly anonymous (200, not 401).
    pub = client.get("/api/v1/books/public/search", params={"q": "databases"})
    assert pub.status_code == 200
    assert pub.json()["total_results"] >= 1


def test_book_catalog_copies_and_search(client, admin_token):
    headers = auth_headers(admin_token)

    book = client.post(
        "/api/v1/books",
        json={
            "format_type": "PHYSICAL",
            "isbn": "978-0262033848",
            "title": "Introduction to Algorithms CLRS",
            "authors": ["Thomas H. Cormen"],
            "category": "Algorithms",
            "publication_year": 2009,
            "rating": 5.0,
            "keywords": ["DSA", "Graph", "Dynamic Programming"],
        },
        headers=headers,
    )
    assert book.status_code == 200

    copy = client.post(
        "/api/v1/books/978-0262033848/copies",
        json={"copy_id": "CLRS-COPY-01", "branch_id": "BRANCH-DELHI"},
        headers=headers,
    )
    assert copy.status_code == 200
    assert copy.json()["copy"]["copy_id"] == "CLRS-COPY-01"

    auto = client.get("/api/v1/books/autocomplete?prefix=Intro", headers=headers)
    assert auto.status_code == 200
    assert len(auto.json()["suggestions"]) >= 1

    search = client.get("/api/v1/books/search?q=algorithms", headers=headers)
    assert search.status_code == 200
    assert search.json()["total_results"] >= 1

    details = client.get("/api/v1/books/978-0262033848", headers=headers)
    assert details.status_code == 200
    assert details.json()["title"] == "Introduction to Algorithms CLRS"

    missing = client.get("/api/v1/books/978-0000000000", headers=headers)
    assert missing.status_code == 404


def test_registration_requires_password(client):
    res = client.post(
        "/api/v1/auth/register",
        json={"user_id": "X", "name": "X", "email": "x@x.com"},
    )
    assert res.status_code == 422


def test_circulation_issue_return_and_concurrency(client, admin_token):
    headers = auth_headers(admin_token)

    # Register a fresh book + single copy, then race two issue requests.
    client.post(
        "/api/v1/books",
        json={
            "format_type": "PHYSICAL",
            "isbn": "978-0000000001",
            "title": "Single Copy Book",
            "authors": ["A"],
            "category": "General",
        },
        headers=headers,
    )
    client.post(
        "/api/v1/books/978-0000000001/copies",
        json={"copy_id": "ONLY-COPY-01", "branch_id": "BRANCH-DELHI"},
        headers=headers,
    )

    # Issue to Alice -> success
    issue = client.post(
        "/api/v1/circulation/issue",
        json={"copy_id": "ONLY-COPY-01", "user_id": "STU-ALICE", "loan_days": 14},
        headers=headers,
    )
    assert issue.status_code == 200
    assert issue.json()["transaction"]["type"] == "BORROW"

    # Second issue of the same copy -> 409 CopyUnavailable
    steal = client.post(
        "/api/v1/circulation/issue",
        json={"copy_id": "ONLY-COPY-01", "user_id": "STU-BOB", "loan_days": 14},
        headers=headers,
    )
    assert steal.status_code == 409

    # Return -> available again
    ret = client.post(
        "/api/v1/circulation/return",
        json={"copy_id": "ONLY-COPY-01", "is_late": False, "is_damaged": False},
        headers=headers,
    )
    assert ret.status_code == 200
    assert ret.json()["status"] == "AVAILABLE"

    # Issuing a non-existent copy -> 404
    nf = client.post(
        "/api/v1/circulation/issue",
        json={"copy_id": "DOES-NOT-EXIST", "user_id": "STU-ALICE", "loan_days": 14},
        headers=headers,
    )
    assert nf.status_code == 404


def test_reservation_auto_assignment(client, admin_token):
    headers = auth_headers(admin_token)

    client.post(
        "/api/v1/circulation/issue",
        json={"copy_id": "DDIA-DEL-01", "user_id": "STU-BOB", "loan_days": 14},
        headers=headers,
    )
    res = client.post(
        "/api/v1/circulation/reserve",
        json={"isbn": "978-1491950357", "user_id": "STU-ALICE"},
        headers=headers,
    )
    assert res.status_code == 200
    assert res.json()["reservation"]["isbn"] == "978-1491950357"

    ret = client.post(
        "/api/v1/circulation/return",
        json={"copy_id": "DDIA-DEL-01", "is_late": False, "is_damaged": False},
        headers=headers,
    )
    assert ret.status_code == 200
    assert ret.json()["auto_assigned_to_reservation"]["user_id"] == "STU-ALICE"


def test_smart_allocation_priority(client, admin_token):
    headers = auth_headers(admin_token)

    a = client.post(
        "/api/v1/circulation/smart-allocation/request",
        json={"isbn": "978-1118063330", "user_id": "STU-ALICE"},
        headers=headers,
    )
    assert a.status_code == 200
    b = client.post(
        "/api/v1/circulation/smart-allocation/request",
        json={"isbn": "978-1118063330", "user_id": "STU-BOB"},
        headers=headers,
    )
    # Bob (exam in 3 days) has stricter exam urgency than Alice (25 days).
    assert b.json()["calculated_priority"] > a.json()["calculated_priority"]

    drop = client.post("/api/v1/circulation/smart-allocation/drop/978-1118063330", headers=headers)
    assert drop.status_code == 200
    assert drop.json()["status"] == "SUCCESS"


def test_intelligence_and_risk(client, admin_token):
    headers = auth_headers(admin_token)

    risk = client.get("/api/v1/intelligence/risk-assessment/STU-RAHUL", headers=headers)
    assert risk.status_code == 200
    assert risk.json()["risk_level"] == "HIGH"
    assert risk.json()["recommended_deposit_amount"] > 0

    recs = client.get("/api/v1/intelligence/recommendations/STU-ISHAAN", headers=headers)
    assert recs.status_code == 200
    assert recs.json()["total"] >= 1

    path = client.get(
        "/api/v1/intelligence/learning-path/978-0262033848",
        params={"depth": 5},
        headers=headers,
    )
    assert path.status_code == 200
    assert len(path.json()["path"]) >= 1

    sp = client.get(
        "/api/v1/intelligence/shortest-path",
        params={"from_isbn": "978-0262033848", "to_isbn": "978-1492040347"},
        headers=headers,
    )
    assert sp.status_code == 200
    assert len(sp.json()["path"]) >= 2


def test_billing_fine_estimate_and_payment(client, admin_token):
    headers = auth_headers(admin_token)

    est = client.get(
        "/api/v1/billing/fine-estimate",
        params={"isbn": "978-1491950357", "user_id": "STU-RAHUL", "overdue_days": 4},
        headers=headers,
    )
    assert est.status_code == 200
    assert est.json()["projected_fine"] > 0

    pay = client.post(
        "/api/v1/billing/pay",
        json={"user_id": "STU-RAHUL", "amount": 30.0, "payment_method": "UPI"},
        headers=headers,
    )
    assert pay.status_code == 200
    assert pay.json()["status"] == "COMPLETED"
    assert pay.json()["remaining_unpaid_balance"] < 120.0


def test_branches_transfer_and_system(client, admin_token):
    headers = auth_headers(admin_token)

    branches = client.get("/api/v1/branches")
    assert branches.status_code == 200
    assert branches.json()["total_branches"] == 3

    trf = client.post(
        "/api/v1/branches/transfer",
        json={"copy_id": "CC-DEL-02", "dest_branch_id": "BRANCH-MUMBAI"},
        headers=headers,
    )
    assert trf.status_code == 200
    assert trf.json()["transfer"]["status"] == "IN_TRANSIT"

    bad_trf = client.post(
        "/api/v1/branches/transfer",
        json={"copy_id": "CC-DEL-02", "dest_branch_id": "BRANCH-NOPE"},
        headers=headers,
    )
    assert bad_trf.status_code == 404

    audit = client.get("/api/v1/system/audit-logs", headers=headers)
    assert audit.status_code == 200
    assert audit.json()["total"] >= 1

    cache = client.get("/api/v1/system/cache-stats", headers=headers)
    assert cache.status_code == 200
    assert "hit_ratio_pct" in cache.json()

    notif = client.get("/api/v1/system/notifications/STU-ALICE", headers=headers)
    assert notif.status_code == 200
    assert isinstance(notif.json()["notifications"], list)


def test_search_pagination(client, admin_token):
    headers = auth_headers(admin_token)

    # Unpaginated/default public search
    pub = client.get("/api/v1/books/public/search")
    assert pub.status_code == 200
    data = pub.json()
    assert "total_results" in data
    assert data["limit"] == 20
    assert data["offset"] == 0
    assert isinstance(data["results"], list)

    # Paginated search with custom limit and offset
    resp = client.get("/api/v1/books/search?limit=2&offset=1", headers=headers)
    assert resp.status_code == 200
    pdata = resp.json()
    assert pdata["limit"] == 2
    assert pdata["offset"] == 1
    assert len(pdata["results"]) <= 2
