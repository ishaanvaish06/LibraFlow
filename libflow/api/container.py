"""
Container assembly for the API layer.

A single ``LibraFlowContainer`` is built once per application lifetime (see
``libflow.api.app.lifespan``) and attached to ``app.state.container``.
``build_container`` resolves the storage backend from ``LIBRAFLOW_STORAGE``;
the other builders are used directly by tests and the seed scripts.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional

from libflow.ai.demand_forecaster import DemandForecaster
from libflow.ai.recommendation_engine import RecommendationEngine
from libflow.ai.risk_assessment import RiskAssessmentModel
from libflow.config import RedisSettings as RedisSettingsCfg
from libflow.distributed.branch_manager import MultiBranchManager
from libflow.dsa.graph import BookGraphEngine
from libflow.dsa.inverted_index import InvertedIndex
from libflow.dsa.trie import AutocompleteTrie
from libflow.patterns.observer_notification import (
    EmailNotificationService,
    InAppNotificationService,
    NotificationDispatcher,
    SmsNotificationService,
)
from libflow.patterns.reservation_queue import BookReservationQueueManager
from libflow.patterns.singleton_logger import AuditLogger
from libflow.services.billing_service import BillingService
from libflow.services.catalog_service import CatalogService
from libflow.services.circulation_service import CirculationService
from libflow.services.intelligence_service import IntelligenceService
from libflow.storage.cache import Cache, InMemoryCache
from libflow.storage.inmemory import (
    InMemoryBookRepository,
    InMemoryBranchRepository,
    InMemoryCirculationRecordRepository,
    InMemoryUserRepository,
)
from libflow.storage.redis_cache import RedisCache
from libflow.storage.repository import (
    BookRepository,
    BranchRepository,
    CirculationRecordRepository,
    UserRepository,
)

from libflow.ai.rebalancer import CrossBranchRebalancingEngine
from libflow.distributed.event_bus import EventBus, InMemoryEventBus, RedisStreamsEventBus
from libflow.storage.lock_manager import ConcurrencyLockManager
from libflow.storage.outbox import OutboxRepository, InMemoryOutboxRepository, PostgresOutboxRepository, OutboxRelay

logger = logging.getLogger(__name__)


def _default_storage_backend() -> str:
    """Resolve the storage backend; defaults to PostgreSQL for the app."""
    return os.getenv("LIBRAFLOW_STORAGE", "postgres").strip().lower()


@dataclass
class LibraFlowContainer:
    storage_backend: str

    book_repo: BookRepository
    user_repo: UserRepository
    branch_repo: BranchRepository
    circulation_repo: CirculationRecordRepository

    cache: Cache

    trie: AutocompleteTrie
    index: InvertedIndex
    graph: BookGraphEngine

    dispatcher: NotificationDispatcher
    email_svc: EmailNotificationService
    sms_svc: SmsNotificationService
    inapp_svc: InAppNotificationService

    reservation_mgr: BookReservationQueueManager
    forecaster: DemandForecaster
    recommender: RecommendationEngine
    branch_mgr: MultiBranchManager
    audit_logger: AuditLogger
    risk_model: RiskAssessmentModel

    catalog_svc: CatalogService
    circulation_svc: CirculationService
    billing_svc: BillingService
    intelligence_svc: IntelligenceService

    rebalancer: Optional[CrossBranchRebalancingEngine] = None
    outbox_repo: Optional[OutboxRepository] = None
    event_bus: Optional[EventBus] = None
    outbox_relay: Optional[OutboxRelay] = None
    lock_manager: Optional[ConcurrencyLockManager] = None

    session_factory: Optional[object] = None
    redis_client: Optional[object] = None

    def dispose(self) -> None:
        if self.outbox_relay is not None:
            self.outbox_relay.stop()
        if self.event_bus is not None and hasattr(self.event_bus, "stop_consumer"):
            self.event_bus.stop_consumer()
        if self.session_factory is not None and hasattr(self.session_factory, "dispose"):
            self.session_factory.dispose()
        if self.redis_client is not None:
            try:
                self.redis_client.close()
            except Exception:  # pragma: no cover - defensive teardown
                pass


def build_in_memory_container() -> LibraFlowContainer:
    book_repo = InMemoryBookRepository()
    user_repo = InMemoryUserRepository()
    branch_repo = InMemoryBranchRepository()
    circulation_repo = InMemoryCirculationRecordRepository()
    cache = InMemoryCache(capacity=5000)
    return _assemble_container(
        storage_backend="memory",
        book_repo=book_repo,
        user_repo=user_repo,
        branch_repo=branch_repo,
        circulation_repo=circulation_repo,
        cache=cache,
    )


def build_postgres_container() -> LibraFlowContainer:
    from libflow.config import DatabaseSettings
    from libflow.storage.postgres import (
        DatabaseSessionFactory,
        PostgresBookRepository,
        PostgresBranchRepository,
        PostgresCirculationRecordRepository,
        PostgresUserRepository,
    )

    settings = DatabaseSettings.from_env()
    session_factory = DatabaseSessionFactory(settings.url)
    redis_settings = RedisSettingsCfg.from_env()
    redis_client = RedisCache.from_settings(
        host=redis_settings.host,
        port=redis_settings.port,
        db=redis_settings.db,
        password=redis_settings.password,
    )

    outbox_repo = PostgresOutboxRepository(session_factory)
    event_bus = RedisStreamsEventBus(redis_client.client)
    lock_manager = ConcurrencyLockManager(redis_client=redis_client.client)

    container = _assemble_container(
        storage_backend="postgres",
        book_repo=PostgresBookRepository(session_factory),
        user_repo=PostgresUserRepository(session_factory),
        branch_repo=PostgresBranchRepository(session_factory),
        circulation_repo=PostgresCirculationRecordRepository(session_factory),
        cache=redis_client,
        outbox_repo=outbox_repo,
        event_bus=event_bus,
        lock_manager=lock_manager,
    )
    container.session_factory = session_factory
    container.redis_client = redis_client
    return container


def build_container(backend: Optional[str] = None) -> LibraFlowContainer:
    chosen = (backend or _default_storage_backend()).lower()
    if chosen == "memory":
        return build_in_memory_container()
    if chosen == "postgres":
        return build_postgres_container()
    raise ValueError(
        f"Unknown storage backend '{chosen}' (expected 'memory' or 'postgres')."
    )


def _assemble_container(
    storage_backend: str,
    book_repo: BookRepository,
    user_repo: UserRepository,
    branch_repo: BranchRepository,
    circulation_repo: CirculationRecordRepository,
    cache: Cache,
    outbox_repo: Optional[OutboxRepository] = None,
    event_bus: Optional[EventBus] = None,
    lock_manager: Optional[ConcurrencyLockManager] = None,
) -> LibraFlowContainer:
    trie = AutocompleteTrie()
    index = InvertedIndex()
    graph = BookGraphEngine()

    dispatcher = NotificationDispatcher()
    email_svc = EmailNotificationService()
    sms_svc = SmsNotificationService()
    inapp_svc = InAppNotificationService()
    dispatcher.subscribe(email_svc)
    dispatcher.subscribe(sms_svc)
    dispatcher.subscribe(inapp_svc)

    if outbox_repo is None:
        outbox_repo = InMemoryOutboxRepository()
    if event_bus is None:
        event_bus = InMemoryEventBus()
    if lock_manager is None:
        lock_manager = ConcurrencyLockManager()

    outbox_relay = OutboxRelay(outbox_repo, event_bus)
    outbox_relay.start()

    reservation_mgr = BookReservationQueueManager(notification_dispatcher=dispatcher)
    forecaster = DemandForecaster()
    recommender = RecommendationEngine(graph_engine=graph)
    branch_mgr = MultiBranchManager()
    audit_logger = AuditLogger()
    risk_model = RiskAssessmentModel.load()

    rebalancer = CrossBranchRebalancingEngine(
        book_repo=book_repo,
        branch_repo=branch_repo,
        branch_mgr=branch_mgr,
        forecaster=forecaster,
        event_bus=event_bus,
    )

    catalog_svc = CatalogService(book_repo, trie, index, cache)
    circulation_svc = CirculationService(
        book_repo,
        user_repo,
        circulation_repo,
        cache,
        reservation_mgr,
        dispatcher,
        forecaster,
        outbox_repo=outbox_repo,
        rebalancer=rebalancer,
    )
    billing_svc = BillingService(book_repo, user_repo, reservation_mgr, dispatcher)
    intelligence_svc = IntelligenceService(
        user_repo, recommender, graph, forecaster, risk_model
    )

    return LibraFlowContainer(
        storage_backend=storage_backend,
        book_repo=book_repo,
        user_repo=user_repo,
        branch_repo=branch_repo,
        circulation_repo=circulation_repo,
        cache=cache,
        trie=trie,
        index=index,
        graph=graph,
        dispatcher=dispatcher,
        email_svc=email_svc,
        sms_svc=sms_svc,
        inapp_svc=inapp_svc,
        reservation_mgr=reservation_mgr,
        forecaster=forecaster,
        recommender=recommender,
        branch_mgr=branch_mgr,
        audit_logger=audit_logger,
        risk_model=risk_model,
        catalog_svc=catalog_svc,
        circulation_svc=circulation_svc,
        billing_svc=billing_svc,
        intelligence_svc=intelligence_svc,
        rebalancer=rebalancer,
        outbox_repo=outbox_repo,
        event_bus=event_bus,
        outbox_relay=outbox_relay,
        lock_manager=lock_manager,
    )