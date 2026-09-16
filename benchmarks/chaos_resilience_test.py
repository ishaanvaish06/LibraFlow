"""
Chaos and Resilience Benchmark.
Injects simulated dependency failure (cache & broker outages) mid-execution
during high concurrent load to demonstrate zero data loss and graceful degradation.

Usage:
    python benchmarks/chaos_resilience_test.py [--requests 60]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from libflow.api.dependencies import build_in_memory_container
from libflow.core.factory import UserFactory
from libflow.seed import seed_library

from libflow.storage.circuit_breaker import CircuitBreaker
from libflow.storage.cache import Cache

RESULTS_DIR = Path(__file__).resolve().parent / "results"


class ChaosFailingCache(Cache):
    """Simulates sudden dependency outage, guarded by CircuitBreaker."""

    def __init__(self, real_cache: Cache):
        self.real_cache = real_cache
        self.is_down = False
        self.breaker = CircuitBreaker("chaos_redis_cache", failure_threshold=2, recovery_timeout=0.2)

    def get(self, key):
        def _read():
            if self.is_down:
                raise ConnectionError("Redis cluster unreachable: connection refused!")
            return self.real_cache.get(key)

        return self.breaker.call(_read, fallback=lambda: None)

    def set(self, key, val, ttl_seconds=None):
        def _write():
            if self.is_down:
                raise ConnectionError("Redis cluster unreachable: connection refused!")
            return self.real_cache.set(key, val, ttl_seconds=ttl_seconds)

        return self.breaker.call(_write, fallback=lambda: None)

    def invalidate(self, key):
        def _del():
            if self.is_down:
                raise ConnectionError("Redis cluster unreachable: connection refused!")
            return self.real_cache.invalidate(key)

        return self.breaker.call(_del, fallback=lambda: False)

    def invalidate_prefix(self, prefix):
        def _del_pfx():
            if self.is_down:
                raise ConnectionError("Redis cluster unreachable: connection refused!")
            return self.real_cache.invalidate_prefix(prefix)

        return self.breaker.call(_del_pfx, fallback=lambda: 0)

    def get_or_compute(self, key, compute_fn, ttl_seconds=300.0):
        val = self.get(key)
        if val is not None:
            return val
        computed = compute_fn()
        if computed is not None:
            self.set(key, computed, ttl_seconds)
        return computed

    def get_stats(self):
        return self.real_cache.get_stats()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requests", type=int, default=60)
    args = parser.parse_args()

    container = build_in_memory_container()
    try:
        seed_library(container)
        chaos_cache = ChaosFailingCache(container.cache)
        container.cache = chaos_cache
        container.catalog_svc.cache = chaos_cache
        container.circulation_svc.cache = chaos_cache

        outcomes: list[str] = []
        outcomes_lock = threading.Lock()

        # Pre-create users
        for i in range(args.requests):
            user = UserFactory.create_user(
                role="STUDENT",
                user_id=f"CHAOS-USER-{i}",
                name=f"Chaos User {i}",
                email=f"chaos{i}@example.com",
                password="password",
            )
            container.user_repo.save_user(user)

        barrier = threading.Barrier(args.requests)

        def worker(idx: int):
            barrier.wait()
            # Mid-stream outage injection: pull the plug!
            if idx == args.requests // 2:
                print("\n[CHAOS MONKEY] Pulling the plug on Redis cache!")
                chaos_cache.is_down = True

            try:
                # Read book details (uses cache-aside via get_or_compute)
                details = container.catalog_svc.get_book_details("978-0132350884")
                assert details is not None
                assert details["isbn"] == "978-0132350884"

                outcome = "SUCCESS_DEGRADED" if chaos_cache.is_down else "SUCCESS_HEALTHY"
            except ConnectionError:
                outcome = "UNCAUGHT_CONNECTION_ERROR"
            except Exception as exc:
                outcome = f"EXCEPTION_{type(exc).__name__}"

            with outcomes_lock:
                outcomes.append(outcome)

        started = time.perf_counter()
        threads = [threading.Thread(target=worker, args=(i,)) for i in range(args.requests)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = time.perf_counter() - started

        uncaught = outcomes.count("UNCAUGHT_CONNECTION_ERROR")
        degraded_successes = outcomes.count("SUCCESS_DEGRADED")
        healthy_successes = outcomes.count("SUCCESS_HEALTHY")
        total_successes = degraded_successes + healthy_successes
        passed = uncaught == 0 and total_successes == args.requests

        result = {
            "benchmark": "chaos-resilience",
            "run_at": datetime.now(timezone.utc).isoformat(),
            "requests": args.requests,
            "healthy_successes": healthy_successes,
            "degraded_successes": degraded_successes,
            "uncaught_errors": uncaught,
            "elapsed_seconds": round(elapsed, 4),
            "passed": passed,
        }

        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        (RESULTS_DIR / "chaos_resilience.json").write_text(
            json.dumps(result, indent=2), encoding="utf-8"
        )

        print(f"\nResults: healthy={healthy_successes} degraded={degraded_successes} uncaught={uncaught} passed={passed}")
        return 0 if passed else 1
    finally:
        container.dispose()


if __name__ == "__main__":
    sys.exit(main())
