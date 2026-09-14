"""
Concurrency stress benchmark.

Races N threads against a single inventory copy to prove the storage-level
per-copy lock yields exactly one successful checkout. This is the headline
"exactly-once under concurrency" demonstration.

Usage:
    python benchmarks/concurrency_stress_test.py [--threads 50]

Exits non-zero if exactly one thread does not win, so CI can gate on it.
Results are persisted to ``benchmarks/results/concurrency_stress.json``.
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

RESULTS_DIR = Path(__file__).resolve().parent / "results"
COPY_ID = "CC-DEL-02"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--threads", type=int, default=50)
    args = parser.parse_args()

    container = build_in_memory_container()
    try:
        seed_library(container)
        issue_svc = container.circulation_svc

        copy = container.book_repo.get_copy(COPY_ID)
        if copy is None or copy.status.value != "AVAILABLE":
            print(f"ERROR: copy {COPY_ID} is not AVAILABLE "
                  f"(status={copy.status.value if copy else 'MISSING'}); "
                  f"check seed_library", file=sys.stderr)
            return 2

        users = [
            UserFactory.create_user(
                role="STUDENT",
                user_id=f"STU-STRESS-{i}",
                name=f"Stress {i}",
                email=f"stress{i}@example.com",
                password="passw0rd",
                academic_year=1,
            )
            for i in range(args.threads)
        ]
        for user in users:
            container.user_repo.save_user(user)

        barrier = threading.Barrier(args.threads)
        outcomes: list[str] = []
        outcomes_lock = threading.Lock()

        def run(user_id: str) -> None:
            barrier.wait()
            try:
                issue_svc.issue_physical_book(COPY_ID, user_id, actor_id="ADMIN-01")
                outcome = "SUCCESS"
            except Exception as exc:
                outcome = type(exc).__name__
            with outcomes_lock:
                outcomes.append(outcome)

        started = time.perf_counter()
        threads = [
            threading.Thread(target=run, args=(user.user_id,)) for user in users
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = time.perf_counter() - started

        successes = outcomes.count("SUCCESS")
        failures = len(outcomes) - successes
        ok = successes == 1 and len(outcomes) == args.threads

        result = {
            "benchmark": "concurrency-stress",
            "run_at": datetime.now(timezone.utc).isoformat(),
            "parameters": {"threads": args.threads, "target_copy": COPY_ID},
            "outcomes": sorted({o: outcomes.count(o) for o in set(outcomes)}.items()),
            "successes": successes,
            "failures": failures,
            "elapsed_seconds": round(elapsed, 4),
            "passed": ok,
        }
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        (RESULTS_DIR / "concurrency_stress.json").write_text(
            json.dumps(result, indent=2), encoding="utf-8"
        )

        print(f"threads={args.threads} successes={successes} failures={failures} "
              f"elapsed={elapsed:.3f}s passed={ok}")
        return 0 if ok else 1
    finally:
        container.dispose()


if __name__ == "__main__":
    sys.exit(main())