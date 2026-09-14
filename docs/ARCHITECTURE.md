# Architecture

This document describes the concrete structure of the LibraFlow codebase as it
is implemented today.

## High-level layer diagram

```
┌─────────────────────────────────────────────────────────────┐
│  REST API  (FastAPI)                                        │
│  libflow/api/{app,routers,auth,dependencies,schemas}.py     │
│  • Lifespan builds a single LibraFlowContainer per process  │
│  • Routes pull services via Depends() — no module singletons│
│  • Centralized exception → HTTP status mapping in app.py    │
└────────────────────────┬────────────────────────────────────┘
                         │  uses
┌────────────────────────▼────────────────────────────────────┐
│  Service layer                                               │
│  libflow/services/{catalog,circulation,billing,              │
│                     intelligence}.py                         │
│  Orchestrate domain operations; no HTTP awareness.           │
└──────┬──────────┬──────────┬───────────┬───────────────────┘
       │          │          │           │
┌──────▼────┐┌───▼──────┐┌──▼────────┐┌─▼──────────────────┐
│ Core      ││ Patterns ││ DSA       ││ AI                  │
│           ││          ││           ││                     │
│ book.py   ││ state    ││ graph.py  ││ recommendation_     │
│ user.py   ││ strategy ││ trie.py   ││   engine.py         │
│ branch.py ││ factory  ││ inv_idx   ││ risk_assessment.py  │
│ enums     ││ observer ││ prio_queue││ demand_forecaster   │
│ exceptions││ singleton││           ││                     │
└─────┬─────┘│ reserv.  │└───────────┘└─────────────────────┘
      │      └─────┬────┘
      │            │
┌─────▼────────────▼────────────────────────────────────────┐
│  Storage layer (Repository interfaces)                     │
│  libflow/storage/{repository,postgres,inmemory,cache,      │
│                   redis_cache,lock_manager}.py              │
│  • BookRepository, UserRepository, BranchRepository,       │
│    CirculationRecordRepository — abstract contracts         │
│  • InMemoryRepository: in-memory dicts + threading.Lock    │
│  • PostgresRepository: SQLAlchemy ORM + SELECT … FOR UPDATE│
│  • InMemoryCache / RedisCache: both implement Cache ABC     │
│  • DatabaseSessionFactory: owns engine + sessionmaker       │
└────────────────────────────────────────────────────────────┘
```

## Container assembly

`LibraFlowContainer` (dataclass in `libflow/api/dependencies.py`) is the
single wiring point. It is built once in the lifespan and stored on
`app.state.container`. The factory `build_container()` reads
`LIBRAFLOW_STORAGE` (`memory` | `postgres`, default `postgres`) and
constructs the appropriate repositories, cache, and services.

In-memory containers are used by every unit test. PostgreSQL containers are
used by the integration tests (see `docker-compose.test.yml`).

```
LibraFlowContainer
├── book_repo:        BookRepository
├── user_repo:        UserRepository
├── branch_repo:      BranchRepository
├── circulation_repo: CirculationRecordRepository
├── cache:            Cache
├── graph:            BookGraphEngine
├── index:            InvertedIndex
├── trie:             AutocompleteTrie
├── forecaster:       DemandForecaster
├── recommender:      RecommendationEngine
├── risk_model:       RiskAssessmentModel (loads shipped joblib)
├── branch_mgr:       MultiBranchManager
├── notification_mgr: NotificationDispatcher
├── audit_logger:     AuditLogger
├── reservation_mgr:  BookReservationQueueManager
├── catalog_svc:      CatalogService
├── circulation_svc:  CirculationService
├── billing_svc:      BillingService
├── intelligence_svc: IntelligenceService
```

## Domain model highlights

| Concept | Implementation | Key file |
|---------|---------------|----------|
| Polymorphic books | `Book` ABC → `PhysicalBook`, `EBook`, `AudioBook` | `libflow/core/book.py` |
| Book copy lifecycle | State pattern (`AvailableState`, `IssuedState`, …) | `libflow/core/book_state.py` |
| RBAC user hierarchy | `User` ABC → `Student`, `Faculty`, `Librarian`, `Admin` | `libflow/core/user.py` |
| Fines / payments | Strategy pattern (fixed + percentage) | `libflow/patterns/strategy_fine.py` |
| Payments | Strategy (UPI, card, wallet, cash) | `libflow/patterns/strategy_payment.py` |
| Notifications | Observer (email, SMS, in-app) | `libflow/patterns/observer_notification.py` |
| Audit log | Singleton | `libflow/patterns/singleton_logger.py` |
| Reservation queue | Priority queue | `libflow/patterns/reservation_queue.py` |
| Autocomplete | Prefix Trie | `libflow/dsa/trie.py` |
| Ranked search | Inverted index + TF-IDF cosine | `libflow/dsa/inverted_index.py` |
| Smart allocation | Max-heap priority queue | `libflow/dsa/priority_queue.py` |
| Book topic graph | Adjacency-list graph + BFS/Dijkstra | `libflow/dsa/graph.py` |
| Recommendation | Content + graph similarity | `libflow/ai/recommendation_engine.py` |
| Risk scoring | Logistic regression (sklearn, shipped joblib) | `libflow/ai/risk_assessment.py` |
| Demand forecasting | Heuristic rule-based | `libflow/ai/demand_forecaster.py` |

## Persistence

**Postgres** — five single-inheritance tables: `books` (JSONB arrays,
discriminator `format`), `book_copies`, `users` (JSONB arrays,
discriminator `role`), `library_branches`, `circulation_records`.
Migration managed by Alembic (`alembic/versions/0001_initial_schema.py`).

**Redis** — cache-aside via `RedisCache`. Keys are plain JSON-serialized.
Connection failures degrade to cache misses (documented trade-off).

## Concurrency control

Every book copy has a per-copy lock:
- **In-memory**: `threading.Lock` per copy_id in `InMemoryBookRepository`.
- **Postgres**: `SELECT … FOR UPDATE` inside `locking_section()`.

This serializes concurrent issue/return requests against the same physical
copy so exactly one request succeeds.

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LIBRAFLOW_STORAGE` | `postgres` | `memory` or `postgres` |
| `DB_HOST` | `localhost` | Postgres host |
| `DB_PORT` | `5432` | Postgres port |
| `DB_NAME` | `libraflow` | Postgres database |
| `DB_USER` | `libraflow_user` | Postgres user |
| `DB_PASSWORD` | `libraflow_secret` | Postgres password |
| `REDIS_HOST` | `localhost` | Redis host |
| `REDIS_PORT` | `6379` | Redis port |
| `LIBRAFLOW_SECRET_KEY` | (fail-fast in prod) | HS256 JWT signing key |
| `ENVIRONMENT` | `development` | `development` / `production` / `test` |
