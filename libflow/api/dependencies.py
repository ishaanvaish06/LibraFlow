"""FastAPI dependency providers.

Container construction lives in ``libflow.api.container``; this module only
declares the ``Depends``-style getters routes use. The builder functions and
``LibraFlowContainer`` are re-exported here so existing imports (tests, seed
scripts, app.py) keep working unchanged.
"""

from __future__ import annotations

from fastapi import Depends, Request

from libflow.ai.recommendation_engine import RecommendationEngine
from libflow.api.container import (
    LibraFlowContainer,
    build_container,
    build_in_memory_container,
    build_postgres_container,
)
from libflow.distributed.branch_manager import MultiBranchManager
from libflow.patterns.observer_notification import InAppNotificationService
from libflow.patterns.reservation_queue import BookReservationQueueManager
from libflow.patterns.singleton_logger import AuditLogger
from libflow.services.billing_service import BillingService
from libflow.services.catalog_service import CatalogService
from libflow.services.circulation_service import CirculationService
from libflow.services.intelligence_service import IntelligenceService
from libflow.storage.cache import Cache
from libflow.storage.repository import (
    BookRepository,
    BranchRepository,
    UserRepository,
)


def get_container(request: Request) -> LibraFlowContainer:
    return request.app.state.container


def get_catalog_service(
    container: LibraFlowContainer = Depends(get_container),
) -> CatalogService:
    return container.catalog_svc


def get_circulation_service(
    container: LibraFlowContainer = Depends(get_container),
) -> CirculationService:
    return container.circulation_svc


def get_billing_service(
    container: LibraFlowContainer = Depends(get_container),
) -> BillingService:
    return container.billing_svc


def get_intelligence_service(
    container: LibraFlowContainer = Depends(get_container),
) -> IntelligenceService:
    return container.intelligence_svc


def get_branch_manager(
    container: LibraFlowContainer = Depends(get_container),
) -> MultiBranchManager:
    return container.branch_mgr


def get_cache(container: LibraFlowContainer = Depends(get_container)) -> Cache:
    return container.cache


def get_inapp_notifications(
    container: LibraFlowContainer = Depends(get_container),
) -> InAppNotificationService:
    return container.inapp_svc


def get_audit_logger(
    container: LibraFlowContainer = Depends(get_container),
) -> AuditLogger:
    return container.audit_logger


def get_user_repository(
    container: LibraFlowContainer = Depends(get_container),
) -> UserRepository:
    return container.user_repo


def get_book_repository(
    container: LibraFlowContainer = Depends(get_container),
) -> BookRepository:
    return container.book_repo


def get_branch_repository(
    container: LibraFlowContainer = Depends(get_container),
) -> BranchRepository:
    return container.branch_repo


def get_reservation_manager(
    container: LibraFlowContainer = Depends(get_container),
) -> BookReservationQueueManager:
    return container.reservation_mgr


def get_recommender(
    container: LibraFlowContainer = Depends(get_container),
) -> RecommendationEngine:
    return container.recommender


__all__ = [
    "LibraFlowContainer",
    "build_container",
    "build_in_memory_container",
    "build_postgres_container",
    "get_container",
    "get_catalog_service",
    "get_circulation_service",
    "get_billing_service",
    "get_intelligence_service",
    "get_branch_manager",
    "get_cache",
    "get_inapp_notifications",
    "get_audit_logger",
    "get_user_repository",
    "get_book_repository",
    "get_branch_repository",
    "get_reservation_manager",
    "get_recommender",
]

