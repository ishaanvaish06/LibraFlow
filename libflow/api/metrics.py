"""
Prometheus Metrics and Distributed Tracing Observability for LibraFlow.
Exposes standard Prometheus metrics (/metrics) for Grafana dashboards,
tracking checkouts, returns, rebalance transfers, latency, and circuit breaker trip states.
"""
from __future__ import annotations

from fastapi import APIRouter, Request, Response
from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    REGISTRY,
    generate_latest,
    CONTENT_TYPE_LATEST,
)

router = APIRouter(tags=["Observability"])

# Metrics Definitions
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests received",
    ["method", "endpoint", "status_code"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

CHECKOUTS_TOTAL = Counter(
    "libflow_checkouts_total",
    "Total physical book copies checked out",
)

RETURNS_TOTAL = Counter(
    "libflow_returns_total",
    "Total book copies returned",
)

REBALANCE_TRANSFERS_TOTAL = Counter(
    "libflow_rebalance_transfers_total",
    "Total autonomous cross-branch transfers initiated",
)

REBALANCE_PRECISION_PCT = Gauge(
    "libflow_rebalance_precision_pct",
    "Percentage of autonomous transfers borrowed within 7 days",
)

CIRCUIT_BREAKER_STATE = Gauge(
    "libflow_circuit_breaker_state",
    "Circuit breaker status (0=CLOSED, 1=HALF_OPEN, 2=OPEN)",
    ["breaker_name"],
)


@router.get("/metrics")
def metrics(request: Request) -> Response:
    """Exposes Prometheus metrics for scraping."""
    # Update live gauges from container if available
    container = getattr(request.app.state, "container", None)
    if container is not None:
        if container.rebalancer is not None:
            m = container.rebalancer.get_outcome_metrics()
            REBALANCE_PRECISION_PCT.set(m.get("precision_rate_pct", 0.0))

        if container.risk_model is not None and hasattr(container.risk_model, "breaker"):
            state = container.risk_model.breaker.state.value
            val = 2 if state == "OPEN" else (1 if state == "HALF_OPEN" else 0)
            CIRCUIT_BREAKER_STATE.labels(breaker_name="ml_risk_scoring").set(val)

        if hasattr(container.cache, "breaker"):
            state = container.cache.breaker.state.value
            val = 2 if state == "OPEN" else (1 if state == "HALF_OPEN" else 0)
            CIRCUIT_BREAKER_STATE.labels(breaker_name="redis_cache").set(val)

    return Response(content=generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)
