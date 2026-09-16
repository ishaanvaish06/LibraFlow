"""
Tests for CircuitBreaker resilience pattern and Prometheus /metrics observability.
"""

from __future__ import annotations

import time
import pytest

from libflow.storage.circuit_breaker import CircuitBreaker, CircuitState
from libflow.ai.risk_assessment import RiskAssessmentModel
from libflow.core.factory import UserFactory


def test_circuit_breaker_transitions():
    breaker = CircuitBreaker("test_service", failure_threshold=2, recovery_timeout=0.1)

    assert breaker.state == CircuitState.CLOSED

    # 1. First failure
    with pytest.raises(ValueError):
        breaker.call(lambda: (_ for _ in ()).throw(ValueError("Call 1 failed")))
    assert breaker.state == CircuitState.CLOSED
    assert breaker.failure_count == 1

    # 2. Second failure trips to OPEN
    with pytest.raises(ValueError):
        breaker.call(lambda: (_ for _ in ()).throw(ValueError("Call 2 failed")))
    assert breaker.state == CircuitState.OPEN

    # 3. Fast fallback while OPEN
    val = breaker.call(lambda: "never called", fallback=lambda: "fallback_value")
    assert val == "fallback_value"

    # 4. Wait for recovery timeout -> probe in HALF_OPEN
    time.sleep(0.12)
    res = breaker.call(lambda: "recovered_success", fallback=lambda: "fallback")
    assert res == "recovered_success"
    assert breaker.state == CircuitState.CLOSED
    assert breaker.failure_count == 0


def test_ml_risk_scoring_degrades_gracefully():
    # Load model and break clf to test degradation
    model = RiskAssessmentModel.load()
    user = UserFactory.create_user(
        role="STUDENT",
        user_id="STU-CIRCUIT",
        name="Circuit User",
        email="circuit@example.com",
        password="pass",
    )

    # Force failure in predict_probability
    def bad_predict(features):
        raise RuntimeError("GPU out of memory / model crash!")

    model.predict_probability = bad_predict

    # Risk evaluation must not raise an exception; it must gracefully degrade
    evaluation = model.evaluate_risk(user)
    assert evaluation["risk_score_pct"] == 5.0
    assert evaluation["risk_level"] == "LOW"
    assert evaluation["require_security_deposit"] is False


def test_prometheus_metrics_endpoint(client):
    resp = client.get("/metrics")
    assert resp.status_code == 200
    text = resp.text
    assert "http_requests_total" in text or "libflow" in text
    assert "libflow_rebalance_precision_pct" in text
