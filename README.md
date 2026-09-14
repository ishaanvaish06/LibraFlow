# LibraFlow

LibraFlow is a library management system built to demonstrate clean OOP design,
GoF design patterns, core data structures, and a REST API layer. Storage is
backed by PostgreSQL; caching by Redis. Recommendation and risk scoring use
classical ML (TF-IDF + cosine similarity, logistic regression) — not deep
learning.

## What is in this repo

- Domain model: polymorphic book hierarchy (`PhysicalBook` / `EBook` /
  `AudioBook`), a State pattern book-copy lifecycle, and an RBAC user hierarchy.
- GoF patterns: State, Strategy (fines, payments), Factory, Observer
  (notifications), Singleton (audit log), plus a priority-queue reservation
  system.
- Data structures: a prefix Trie for autocomplete, an inverted index for
  ranked search, a max-heap priority queue for smart allocation, and an
  adjacency-list graph for topic traversal.
- Machine learning: a hybrid content + graph similarity recommendation engine
  and a logistic-regression late-return risk model (trained from seeded
  circulation data).
- REST API: FastAPI with JWT (HS256) auth, RBAC and centralized error handling.

## Design Decisions & Trade-offs

- **Repository pattern** — services talk to abstract contracts
  (`BookRepository`, `UserRepository`, …) so storage is swappable:
  in-memory dicts for instant tests, PostgreSQL via SQLAlchemy in
  production. Nothing in a service imports an ORM.
- **Pessimistic locking for copy issue/return** — a per-copy
  `threading.Lock` (in-memory) or `SELECT … FOR UPDATE` (Postgres) guarantees
  exactly one concurrent checkout succeeds (see benchmark below).
- **Redis cache-aside** — reads populate the cache; writes invalidate keys.
  Redis failures degrade to cache misses, never to server errors.
- **Centralized exception mapping** — every domain exception is translated to
  an HTTP status in exactly one place (`libflow/api/app.py`). Services never
  raise `HTTPException`.
- **Memoised bcrypt salts** — passwords are hashed once per unique string
  per process so the 40+ tests seed in ~4s instead of ~55s. Production
  deployments can disable this (see `docs/DECISIONS.md`).
- **Shipped ML model** — the logistic-regression risk model is committed as
  `models/risk_model.joblib` after an offline training run, so live
  predictions need no training pipeline.

Everything — including why there is no NoSQL store, how the model is
trained, and migration strategy — is in `docs/DECISIONS.md`.

## Run it locally

Requires Docker with Postgres 16 and Redis 7:

```bash
docker compose up --build
```

The API is served at `http://localhost:8000` with OpenAPI docs at
`http://localhost:8000/docs`. See `docs/RUNBOOK.md` for migrations, seeding,
running tests, and the integration-test workflow.

## Tests & benchmarks

```bash
python -m pytest tests/                     # unit tests (in-memory doubles, ~4s)
python -m pytest tests/integration/         # needs Docker Postgres + Redis
python benchmarks/concurrency_stress_test.py        # exactly-one-success proof
python benchmarks/run_load_benchmark.py             # headless locust load test
```

Latest results: [concurrency](benchmarks/results/concurrency_stress.json),
[load test](benchmarks/results/load_benchmark.json). See
[`docs/RUNBOOK.md`](docs/RUNBOOK.md) for all operational procedures.

## More docs

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — layer & container diagram,
  persistence, concurrency model.
- [`docs/DECISIONS.md`](docs/DECISIONS.md) — every trade-off, with the
  reasoning behind it.
- [`docs/RUNBOOK.md`](docs/RUNBOOK.md) — run/local/Docker/migrations/testing.
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — conventions and workflow.