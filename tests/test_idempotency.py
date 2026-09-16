"""
Tests for API Idempotency Keys across checkout, return, and payment endpoints.
"""

from __future__ import annotations

import uuid
import pytest

from tests.conftest import auth_headers
from libflow.api.idempotency import IdempotencyStore, handle_idempotent_operation
from fastapi import HTTPException


def test_idempotency_store_direct():
    store = IdempotencyStore()
    key = str(uuid.uuid4())

    # Not found
    assert store.get(key) is None

    # Set in progress
    assert store.set_in_progress(key, timeout_seconds=10) is True
    # Duplicate in progress rejected
    assert store.set_in_progress(key, timeout_seconds=10) is False

    # Mark completed
    store.set_completed(key, 200, {"result": "success"})
    cached = store.get(key)
    assert cached is not None
    assert cached["status"] == "COMPLETED"
    assert cached["response_body"]["result"] == "success"


def test_handle_idempotent_operation():
    store = IdempotencyStore()
    key = str(uuid.uuid4())
    execution_count = 0

    def work():
        nonlocal execution_count
        execution_count += 1
        return {"count": execution_count}

    # First run executes
    res1 = handle_idempotent_operation(key, store, work)
    assert res1["count"] == 1
    assert execution_count == 1

    # Second run with same key returns cached response and does not re-execute work()
    res2 = handle_idempotent_operation(key, store, work)
    assert res2["count"] == 1
    assert execution_count == 1


def test_api_issue_idempotency(client, admin_token):
    headers = auth_headers(admin_token)
    idemp_key = f"IDEMP-ISSUE-{uuid.uuid4().hex[:8]}"
    headers["Idempotency-Key"] = idemp_key

    payload = {
        "copy_id": "CC-DEL-01",
        "user_id": "STU-BOB",
        "loan_days": 14,
    }

    # 1. First checkout attempt succeeds
    resp1 = client.post("/api/v1/circulation/issue", json=payload, headers=headers)
    assert resp1.status_code == 200
    tx1 = resp1.json()["transaction"]["transaction_id"]

    # 2. Retrying with identical Idempotency-Key returns exactly same transaction ID (no double checkout error!)
    resp2 = client.post("/api/v1/circulation/issue", json=payload, headers=headers)
    assert resp2.status_code == 200
    tx2 = resp2.json()["transaction"]["transaction_id"]
    assert tx1 == tx2


def test_api_billing_pay_idempotency(client, admin_token):
    headers = auth_headers(admin_token)
    idemp_key = f"IDEMP-PAY-{uuid.uuid4().hex[:8]}"
    headers["Idempotency-Key"] = idemp_key

    payload = {
        "user_id": "STU-ALICE",
        "amount": 10.0,
        "payment_method": "UPI",
        "payment_metadata": {"vpa": "alice@okaxis"},
    }

    # First payment succeeds
    p1 = client.post("/api/v1/billing/pay", json=payload, headers=headers)
    assert p1.status_code == 200
    tx1 = p1.json()["transaction_id"]

    # Retrying with same key returns cached payment receipt
    p2 = client.post("/api/v1/billing/pay", json=payload, headers=headers)
    assert p2.status_code == 200
    tx2 = p2.json()["transaction_id"]
    assert tx1 == tx2
