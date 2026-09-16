"""
FastAPI application for LibraFlow.

Container is built once per process lifetime inside the lifespan handler
and attached to ``app.state.container``. Every route pulls its services
through ``Depends(get_container)`` — no route imports module-level
singletons.
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from libflow.api.dependencies import build_container, LibraFlowContainer
from libflow.core import exceptions as exc
from .routers import auth, billing, branches, catalog, circulation, intelligence, rebalance, system

logger = logging.getLogger(__name__)

_START_TIME = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    container = build_container()
    app.state.container = container
    if container.storage_backend == "memory":
        from libflow.seed import seed_library
        seed_library(container)
        logger.info("Seeded in-memory catalog and users.")
    logger.info(
        "LibraFlow started [storage=%s, uptime=%.1fs]",
        container.storage_backend,
        time.time() - _START_TIME,
    )
    try:
        yield
    finally:
        container.dispose()
        logger.info("LibraFlow shutdown complete.")


app = FastAPI(
    title="LibraFlow – Library Management System",
    version="0.2.0",
    description=(
        "Repository-structured library management API. "
        "Postgres/Redis infrastructure with DSA-driven scheduling and "
        "ML-backed late-return risk prediction."
    ),
    lifespan=lifespan,
)

# -- Centralized error mapping ------------------------------------------------
_STATUS_MAP = {
    exc.NotFoundError: 404,
    exc.DuplicateResourceError: 409,
    exc.InvalidStateTransitionError: 409,
    exc.CopyUnavailableError: 409,
    exc.UserNotEligibleError: 409,
    exc.OptimisticLockConflictError: 409,
    exc.PermissionDeniedError: 403,
    exc.InsufficientInputError: 400,
    exc.TransferError: 400,
    exc.DomainError: 400,
}

for _exc_cls, _code in _STATUS_MAP.items():
    app.add_exception_handler(_exc_cls, lambda r, e, c=_code: JSONResponse(status_code=c, content={"error": str(e)}))  # type: ignore[arg-type]

app.add_exception_handler(ValueError, lambda r, e: JSONResponse(status_code=400, content={"error": str(e)}))  # type: ignore[arg-type]

# -- Routers ------------------------------------------------------------------
app.include_router(auth.router)
app.include_router(catalog.router)
app.include_router(circulation.router)
app.include_router(billing.router)
app.include_router(intelligence.router)
app.include_router(branches.router)
app.include_router(rebalance.router)
app.include_router(system.router)
from libflow.api.metrics import router as metrics_router
app.include_router(metrics_router)


@app.get("/", include_in_schema=False)
def _root() -> dict[str, str]:
    return {"service": "LibraFlow", "docs": "/docs"}