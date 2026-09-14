# Design Decisions & Trade-offs

Every non-obvious choice in the codebase has a reason. This document captures
the major ones and the trade-offs accepted.

## 1. In-memory repository doubles vs real Postgres-only

**Decision:** Every repository interface (`BookRepository`, `UserRepository`,
etc.) has an in-memory implementation backed by dicts and a threading lock.

**Why:** Tests run in ~4 seconds with no external dependencies. CI never
fails due to a flaky database. The Postgres repository implements the same
interface, so switching is a one-line factory change.

**Trade-off:** The in-memory repos do not enforce FK constraints, JSONB
array semantics, or transaction isolation beyond `threading.Lock`. The
integration suite (`tests/integration/`) validates these properties against
a real Postgres and must be run via Docker.

## 2. Repository pattern vs direct ORM in services

**Decision:** Services depend on abstract repository contracts; they never
import SQLAlchemy.

**Why:** Business logic remains testable with doubles. Storage can be swapped
without touching service code. The Alembic migration owns schema changes;
services own domain rules.

**Trade-off:** Slightly more plumbing per new operation (a method on the
interface, an implementation in both backends). The added indirection pays
off whenever a repository method is tested or replaced.

## 3. Pessimistic locking for book copy issue/return

**Decision:** `locking_section(copy_id)` uses `SELECT … FOR UPDATE`
(Postgres) or a per-copy `threading.Lock` (in-memory). All other
operations use the default autocommit session.

**Why:** Book copy issue/return is the one operation where two users
racing for the same physical copy must yield exactly one winner. Every
other domain rule tolerates eventual consistency.

**Trade-off:** Pessimistic locks increase Postgres lock contention under
extreme load. The concurrency benchmark (50 threads) shows the system
degrades gracefully — exactly one succeeds, the rest receive
`CopyUnavailableError` immediately.

## 4. JWT auth with no refresh token

**Decision:** Login returns a short-lived bearer token (default 60 min).
There is no refresh flow.

**Why:** The system is designed for interactive browser/API sessions, not
long-lived machine-to-machine tokens. A single token per session keeps the
implementation honest and avoids refresh-token rotation complexity.

**Trade-off:** Users must re-authenticate after the token expires. A
refresh endpoint could be added without structural changes.

## 5. Password hashing: memoised bcrypt salts

**Decision:** `hash_password` is memoised per unique password string. All
seed users share "passw0rd"; the admin uses "admin123".

**Why:** The seed pipeline creates 7 users across 40+ tests. Without
memoisation, repeated bcrypt runs (cost 12) dominate setup time, blowing
the suite past 15 seconds. Memoisation brings it to ~4 seconds.

**Trade-off:** Identical passwords receive the same salt within a process.
An attacker with a single process dump can build a per-password lookup.
This is acceptable for a demo; production deployments should clear the
cache between registration requests or set `maxsize=0` in `lru_cache`.

## 6. Redis cache-aside with graceful degradation

**Decision:** `RedisCache` methods catch `redis.RedisError` and return
`None` / `0` instead of raising.

**Why:** Redis is an acceleration layer, not a source of truth. When Redis
is unavailable, every read should fall through to the database rather than
returning a 500.

**Trade-off:** A stale cache after Redis recovers is possible. The
invalidation-on-write pattern (invalidate on mutation) minimizes this
window. Full cache flush on recovery is documented as a future enhancement.

## 7. Centralized exception mapping

**Decision:** All domain exceptions are caught once in `app.py` and mapped
to HTTP status codes. Services never raise `HTTPException`.

**Why:** Domain code is decoupled from HTTP transport. A future gRPC or
CLI interface can translate the same exceptions differently.

**Trade-off:** A single handler means a single status-code decision for
each exception type. Fine-grained per-route overrides are not supported.
This is acceptable because the exception vocabulary is specific enough
(`CopyUnavailableError` → 409, `PermissionDeniedError` → 403).

## 8. Shipped ML model (joblib)

**Decision:** The risk assessment model is trained once via
`scripts/train_risk_model.py` and committed as `models/risk_model.joblib`.

**Why:** Training produces a deterministic model from a reproducible seed
dataset. Committing it means the API serves risk predictions without a
training pipeline at runtime.

**Trade-off:** The model drifts if the seed data distribution changes. A
retraining schedule is documented in `docs/RUNBOOK.md` as a future
enhancement.

## 9. Single-table inheritance for books and users

**Decision:** `books` and `users` use a discriminator column (`format` /
`role`) rather than joined table inheritance.

**Why:** The polymorphic variants share most columns. Single-table avoids
JOINs on common queries (search, list, recommendations). JSONB columns
(`authors`, `keywords`) carry variant-specific data without extra tables.

**Trade-off:** Queries returning mixed types load unused columns. This is
negligible with the current catalog size.

## 10. No WebSocket / streaming for notifications

**Decision:** In-app notifications are pulled via REST polling.

**Why:** The system is designed for human users browsing a catalog. WebSockets
add deployment complexity (sticky sessions, connection pools) with limited
benefit for the intended usage pattern.

**Trade-off:** Notification delivery latency is bounded by the polling
interval. A push-based channel can be added via the Observer pattern
without changing the notification domain.
