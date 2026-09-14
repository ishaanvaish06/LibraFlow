# Runbook

How to build, run, seed, test, and benchmark LibraFlow locally and in CI.

## Prerequisites

- Python 3.12+ (tested on 3.14.7)
- Docker + Docker Compose (for Postgres/Redis and integration tests)
- `pip install -r requirements.txt`

---

## Quick start (in-memory, no Docker)

```bash
# Set up in-memory storage
export LIBRAFLOW_STORAGE=memory

# Start the API (auto-seeds 8 books, 7 users, 3 branches)
python -m uvicorn libflow.api.app:app --reload
# http://localhost:8000/docs

# Run the unit suite (~4 seconds)
python -m pytest tests/ -q
```

## Seed data

| User ID | Role | Password |
|---------|------|----------|
| `ADMIN-01` | Admin | `admin123` |
| `STU-ALICE` | Student | `passw0rd` |
| `STU-BOB` | Student | `passw0rd` |
| `STU-ISHAAN` | Student | `passw0rd` |
| `STU-RAHUL` | Student | `passw0rd` |
| `FAC-DR-SHARMA` | Faculty | `passw0rd` |
| `LIB-SARAH` | Librarian | `passw0rd` |

To re-seed a running server: call `POST /api/v1/auth/register` for each
user, or restart with `LIBRAFLOW_STORAGE=memory` (lifespan auto-seeds).

---

## Docker (Postgres + Redis)

```bash
# Build and start all services
docker compose up --build

# Apply migration + seed
docker compose run --rm api alembic upgrade head
docker compose run --rm api python scripts/seed_data.py

# Stop and clean up
docker compose down -v
```

The API is served at `http://localhost:8000`.

---

## Alembic migrations

```bash
# Generate a new migration (requires a live DB)
alembic revision --autogenerate -m "description"

# Apply
alembic upgrade head

# Roll back
alembic downgrade -1
```

Migration files live in `alembic/versions/`. The initial migration
(`0001_initial_schema.py`) creates all five tables.

---

## Running the test suite

```bash
# Unit tests (in-memory, ~4 seconds)
python -m pytest tests/ -q

# With coverage on core/patterns/dsa
python -m pytest tests/ -q \
    --cov=libflow.core --cov=libflow.patterns --cov=libflow.dsa \
    --cov-report=term --cov-config=pyproject.toml

# Integration tests (Postgres + Redis via Docker)
docker compose -f docker-compose.test.yml up --build --abort-on-container-exit
```

Integration tests are automatically skipped when `TEST_DATABASE_URL` /
`TEST_REDIS_HOST` environment variables are not set.

---

## Benchmarks

### Concurrency stress (exactly-one-success proof)

```bash
python benchmarks/concurrency_stress_test.py --threads 50
# Exit 0 iff exactly 1 thread succeeds.
# Results: benchmarks/results/concurrency_stress.json
```

### Locust load test

```bash
# Option A: manual (start server in one terminal, locust in another)
LIBRAFLOW_STORAGE=memory python -m uvicorn libflow.api.app:app --port 8000
locust -f benchmarks/load_test.py --host http://127.0.0.1:8000 --headless \
       -u 50 -r 10 --run-time 30s

# Option B: automated (starts server, runs locust, reports)
python benchmarks/run_load_benchmark.py --threads 50 --ramp 10 --run-time 30s
# Results: benchmarks/results/load_benchmark.json
```

---

## Re-training the risk model

```bash
python scripts/train_risk_model.py
# Produces models/risk_model.joblib
```

The model is committed to the repository. Retrain if the seed data
distribution changes or feature logic is modified.

---

## Project layout

```
libflow/
├── api/          FastAPI app, routers, auth, DI
├── core/         Domain models, enums, exceptions, factory
├── ai/           Recommendation engine, risk model, demand forecaster
├── dsa/          Trie, inverted index, priority queue, graph
├── patterns/     Observer, strategy, singleton, reservation queue
├── services/     Business logic (catalog, circulation, billing, intelligence)
├── storage/      Repository interfaces, Postgres + in-memory impls, cache
└── seed.py       Shared seeding used by tests, scripts, and Docker entrypoint
```
