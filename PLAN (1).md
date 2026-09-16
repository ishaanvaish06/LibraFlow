# LibraFlow — System Design Integration & Innovation Plan

_Audit date: 2026-09-15. Based on cloning and running the actual repo (48/48 tests,
one import bug found and fixed; full commit history inspected; coverage measured; live
architecture read file-by-file), not the README's description of itself._

---

## 0. Brutal baseline: what LibraFlow actually is today

Before any plan, be honest about the starting point, because the gap between the two
is the plan.

| Claim in README/commits | Reality in the code |
|---|---|
| "Distributed Scale" | `distributed/event_bus.py` is a `threading.Lock`-guarded Python dict of callables in one process. No network hop, no second node, ever. |
| "Multi-branch network synchronization" | Branch transfer is a manually-triggered state machine (`InterBranchTransferRequest`) — no automatic rebalancing, no consensus, no partition handling. |
| "High-concurrency safeguards" | Real and correct for a single process (`threading.Lock` per copy, Postgres `SELECT ... FOR UPDATE`) — but a `threading.Lock` **does nothing across two API replicas**. Scale the API horizontally today and double-checkout comes back. |
| "Production-grade" | `storage/postgres.py` 28% covered, `storage/redis_cache.py` 25% covered, by 8 integration tests that require Docker and have never run in CI — because there is no CI. |
| "Predictive AI/ML" | Real `LogisticRegression`, real feature engineering — trained on synthetic seed data, evaluated with a single train/test accuracy number, no ROC-AUC/precision-recall, no calibration. |
| 3-phase engineering narrative | 3 git commits total, two of which are full-codebase dumps ("LIBFLOW V1.0", "Phases 0-5 remediation"). No incremental history for an interviewer to read. |

None of this is disqualifying — the OOP, patterns, and single-node concurrency work is
genuinely solid. But **"integrate system design" cannot mean adding more service names
to a folder structure.** It has to mean making the distributed claims true, at a scale
where the interesting problems (partial failure, ordering, idempotency, backpressure)
actually show up. That's the plan below.

---

## 1. What "innovative" actually means here

The generic version of this project (CRUD + JWT + Postgres + Redis) is already built.
Copying "add microservices + Kafka" onto it without a reason is cargo-culting, and
experienced interviewers can tell. The plan below is built around **one genuinely novel
feature** that only makes sense once the system is actually distributed, so the system
design work has a real purpose instead of being decorative:

> **Cross-Branch Inventory Rebalancing Engine**: the system already has demand
> forecasting (`DemandForecaster`), a priority queue (`SmartAllocationQueue`), and a
> graph (adjacency list for topic/branch relationships) — but they're disconnected
> demos. Wire them into a real optimization loop that watches demand signals across
> branches, computes the highest-value copy transfers under constraints (transfer cost,
> truck routes, urgency), and **executes them autonomously through an event pipeline**,
> not through a human clicking "transfer" in Postman.

This gives every system-design pattern below a concrete reason to exist instead of
being résumé keywords: the rebalancing decision has to survive a branch service being
down, has to not double-move the same copy, has to not spam the same transfer if an
event is redelivered, and has to be observable when it makes a bad call. That's exactly
where CQRS, outbox, idempotency, and observability stop being buzzwords.

---

## 2. Target architecture

### 2.1 Before (today)

```
┌─────────────┐     ┌───────────┐     ┌───────┐
│   FastAPI   │────▶│ PostgreSQL│     │ Redis │
│  (monolith) │────▶└───────────┘     │ cache │
└─────────────┘────────────────────────▶└───────┘
   single process, threading.Lock, in-memory event bus
```

### 2.2 After (target)

```
                        ┌────────────────────┐
                        │   API Gateway /     │
  clients ────────────▶│   Nginx (LB, TLS)   │
                        └─────────┬───────────┘
                                  │
        ┌─────────────┬──────────┼───────────┬──────────────┐
        ▼             ▼          ▼            ▼              ▼
 ┌────────────┐ ┌───────────┐ ┌────────┐ ┌───────────┐ ┌──────────────┐
 │  Catalog   │ │Circulation│ │Billing │ │Intelligence│ │ Notification │
 │  Service   │ │  Service  │ │Service │ │  Service   │ │   Service    │
 │ (N replicas)│ │(N replicas)│ │       │ │ (rebalancer│ │ (WebSocket + │
 │            │ │            │ │       │ │  + risk ML)│ │  email/SMS)  │
 └─────┬──────┘ └─────┬──────┘ └───┬───┘ └─────┬──────┘ └──────┬───────┘
       │              │            │           │                │
       │        ┌─────▼────────────▼───────────▼────────────────▼─────┐
       │        │      Redis Streams / RabbitMQ (event backbone)       │
       │        │  topics: copy.issued, copy.returned, demand.spiked,  │
       │        │  transfer.requested, transfer.completed, fine.raised │
       │        └────────────────────┬───────────────────────────────┘
       │                             │
       ▼                             ▼
 ┌──────────────┐          ┌──────────────────┐
 │ Postgres      │         │  Outbox table per  │
 │ (per-service  │◀────────│  service (reliable │
 │ schema, or    │         │  event publish)     │
 │ shared w/     │         └──────────────────┘
 │ row-level     │
 │ ownership)    │
 └──────────────┘
       ▲
       │  Redis Redlock (cross-process distributed lock,
       │  replaces threading.Lock — required once >1 replica exists)
```

Key point: **this doesn't have to be 5 separate deployables on day one.** Ship it as a
"modular monolith with a real message bus and a real distributed lock" first (Phase 2),
prove the event-driven pieces work, *then* physically split services (Phase 4) once
there's something worth splitting. Splitting prematurely just adds YAML, not skill
demonstration.

---

## 3. System design concepts to implement, and exactly where they attach

Each row is a concept an interviewer will ask about — mapped to the specific place in
*this* codebase where it becomes real, not abstract.

| Concept | Where it lands | Why it's not decorative here |
|---|---|---|
| **Distributed locking** | Replace `ConcurrencyLockManager`'s `threading.Lock` with Redis-based Redlock (or Postgres advisory locks) for copy checkout | Your own audit already proved the in-process lock breaks the moment you run 2 API replicas. This is a real bug fix, not a feature. |
| **Outbox pattern** | `CirculationService.issue_physical_book` / `return_physical_book` write the DB row and the event in the same transaction, a relay publishes to the bus | Right now `dispatcher.dispatch()` fires in-process after the DB commit — if the process crashes between commit and dispatch, the event is lost silently. Outbox fixes this for real. |
| **Idempotency keys** | Every write endpoint (`POST /circulation/issue`, transfer creation) accepts a client-supplied idempotency key stored with a TTL | Needed the moment you have retries from a load balancer or a message consumer that redelivers — otherwise a retried "issue book" call double-charges a fine or double-decrements inventory. |
| **CQRS (light)** | Catalog search/autocomplete reads from a denormalized read model (kept warm via the inverted index + Redis) while writes go through `CatalogService` | You already built an inverted index and a trie — CQRS is just formalizing "writes update the source of truth, a projection keeps the search structures in sync via events" instead of updating them inline. |
| **Event-driven rebalancing** | New `RebalancingEngine` subscribes to `copy.returned` / `demand.spiked` events, runs an optimization pass, emits `transfer.requested` | This is the innovation feature — see §4. |
| **Circuit breaker / bulkhead** | Wrap the Redis cache and the ML risk-scoring call so a slow/down dependency degrades to "skip cache" / "skip risk check" instead of hanging the request | You already claim "Redis failures degrade to cache misses" in DECISIONS.md — make that a real, tested circuit breaker (e.g. `pybreaker`) instead of a bare `try/except`. |
| **Backpressure / rate limiting** | Token-bucket rate limit per user on the API gateway layer, and consumer-side pacing on the rebalancing engine so it can't fire more than N transfers/minute | Prevents the rebalancer from oscillating copies back and forth if demand signals are noisy — a real failure mode you can demo and fix. |
| **Observability** | OpenTelemetry traces across the checkout → event → rebalance path, Prometheus metrics, a Grafana dashboard | This is what turns "I built microservices" into "I can debug microservices" — the more impressive claim in an interview. |
| **Chaos / resilience testing** | A script that kills the Redis/broker container mid-load-test and shows the system degrades instead of corrupting data | Directly answers "how do you know your distributed system is correct?" — most portfolios never attempt this, which is exactly why it stands out. |
| **Pagination + cursoring** | Fix `GET /api/v1/books/search` (currently returns everything, unbounded) | Small, but a reviewer who runs your API for 30 seconds will hit this immediately. |

---

## 4. The innovation feature, specified

**Cross-Branch Inventory Rebalancing Engine**

- **Trigger**: `DemandForecaster` already computes `demand_category` per ISBN
  (`NORMAL`/`MODERATE`/`SURGE`) from checkout velocity. Wire it to actually *emit* a
  `demand.spiked` event when a title crosses into `SURGE` at one branch while sitting
  idle (`AVAILABLE`, uncirculated for N days) at another.
- **Decision**: A rebalancing pass runs on a schedule (or on event) and solves a small
  constrained optimization: given a set of (branch, copy, idle-days) and a set of
  (branch, isbn, demand-pressure), choose transfers that maximize predicted
  demand-satisfaction minus transfer cost (distance between branches, using the
  existing adjacency-list graph you already built for exactly this kind of traversal),
  subject to a max-transfers-in-flight-per-branch constraint. This is a genuinely good
  algorithms interview story: "I modeled it as a bipartite assignment / min-cost-flow
  problem and used \<X\>" — pick either a simple greedy-by-priority-queue (cheap, you
  already have `SmartAllocationQueue`) or, to go further, a small LP via `scipy.optimize.linprog`
  for a proper min-cost transportation problem.
- **Execution**: Emits `transfer.requested` events, consumed idempotently by the branch
  manager, which drives the existing `InterBranchTransferRequest` state machine —
  autonomously, no human triggering it via Postman.
- **Feedback loop**: Track whether autonomous transfers actually got borrowed
  post-arrival (a simple precision metric: "% of proactive transfers checked out within
  7 days of arrival"), and surface it on a small dashboard. This closes the loop and
  gives you a real "did my system's decision work" metric to talk about — most students'
  projects never measure whether their "smart" feature actually helped.

This single feature exercises: DSA (graph, priority queue, or LP), ML (demand
forecasting feeding a decision), distributed systems (event bus, idempotency, eventual
consistency across branches), and product thinking (a measurable outcome). That's the
"innovative" part — not a new buzzword, a closed loop.

---

## 5. Phased roadmap

### Phase 0 — Credibility repairs (do this first, ~1 day)
- [ ] Fix the `Optional` import bug (blocking crash) — already identified.
- [ ] Add GitHub Actions CI: ruff + mypy + pytest + coverage badge. This alone would
      have caught Phase 0's bug automatically — good thing to say in an interview.
- [ ] Add pagination to `/books/search`.
- [ ] Tone down README claims ("distributed", "production-grade") to match what's true
      *right now* — you'll earn the words back in later phases, and an inflated README
      that gets contradicted by 10 minutes of code reading is worse than an honest one.
- [ ] From here on: small, real, incremental commits. No more full-codebase dumps.

### Phase 1 — Make concurrency actually distributed-safe (~2-3 days)
- [ ] Swap `threading.Lock` for Redis-based distributed locking (Redlock or simple
      `SET NX PX` + Lua unlock script) in `ConcurrencyLockManager`.
- [ ] Run the API as 2+ replicas behind Nginx locally via docker-compose; re-run the
      existing concurrency stress benchmark against the replicated setup and confirm
      "exactly one success" still holds. Publish before/after results.

### Phase 2 — Event backbone + outbox (~1 week)
- [ ] Stand up Redis Streams (simplest) or RabbitMQ (more "real" for an interview, more
      setup cost — pick based on how much you want to talk about broker semantics).
- [ ] Add an `outbox_events` table; `CirculationService` writes business row + event row
      in one DB transaction; a small relay polls the outbox and publishes.
- [ ] Move `NotificationDispatcher` to consume from the bus instead of being called
      in-process.
- [ ] Add idempotency keys to `issue`/`return`/`pay-fine` endpoints.

### Phase 3 — The innovation feature (~1-2 weeks)
- [ ] Build `RebalancingEngine` as described in §4, starting with the greedy/priority-queue
      version, event-driven end to end.
- [ ] Add the outcome-tracking metric (did the transferred copy get borrowed).
- [ ] Write this up as its own README section with a diagram — this is the section a
      recruiter or interviewer should read first.

### Phase 4 — Resilience & observability (~1 week)
- [ ] Circuit breaker around Redis cache and the ML risk call.
- [ ] OpenTelemetry tracing + Prometheus + a Grafana dashboard for the
      checkout → event → rebalance path.
- [ ] Chaos test: kill the broker/Redis mid-load-test, demonstrate no data corruption
      and documented degraded behavior (not a crash).

### Phase 5 — Optional: physical service split (~1-2 weeks, only if Phases 1-4 land well)
- [ ] Split Catalog / Circulation / Billing / Intelligence into separately deployable
      services sharing the event bus, each with its own DB schema.
- [ ] API gateway in front, service-to-service auth (mTLS or signed JWT passthrough).
- [ ] Only do this once there's a real reason (independent scaling, independent
      deploys) — don't split just to have more boxes in a diagram.

### Phase 6 — Make it visible (ongoing, do in parallel)
- [ ] Deploy a live instance (Render/Fly/Railway) with seeded demo data + Swagger link
      in the README.
- [ ] Small React/HTML dashboard showing live branch inventory + rebalancing decisions
      via WebSocket — this is what turns "read my code to believe it" into "click here."
- [ ] Record a 60-90 second demo video/GIF: issue a book at Branch A, watch the
      rebalancer notice a spike at Branch B, watch a transfer get proposed and executed.

---

## 6. What to explicitly cut or not build

To keep this from sprawling into an unfinished 6-month project:
- Don't build a real message queue *and* Kafka *and* gRPC *and* Kubernetes — pick Redis
  Streams or RabbitMQ, and docker-compose is a fine deployment story for a portfolio.
  Depth on one broker beats shallow coverage of five technologies.
- Don't do the full physical service split (Phase 5) unless Phases 1-4 are solid —
  an interviewer will much rather see 3 phases done rigorously with real failure
  testing than 6 phases scaffolded but untested.
- Don't add more ML models. One well-evaluated model (with proper metrics, per the
  earlier review) is worth more than three shallow ones.

## 7. Definition of "done" for "outstanding"

You'll know this is portfolio-ready when you can answer, with evidence in the repo, not
just claims in the README:
1. "What happens if two API instances try to check out the same copy at once?" →
   point to the Redis lock + the stress test re-run against 2 replicas.
2. "What happens if your message broker goes down mid-checkout?" → point to the outbox
   table and the chaos test results.
3. "How do you know the rebalancing engine actually helps?" → point to the outcome
   metric.
4. "Walk me through how this evolved" → point to a real, incremental commit history,
   not two giant dumps.
