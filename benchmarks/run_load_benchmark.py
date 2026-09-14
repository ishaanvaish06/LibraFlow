"""
End-to-end load benchmark.

Spins up an in-memory LibraFlow server, waits for readiness, then runs a
headless Locust load test. A summary JSON is written to
``benchmarks/results/load_benchmark.json``.

Usage:
    python benchmarks/run_load_benchmark.py [--threads 50 --ramp 10 --run-time 30s]

Requires locust (already in requirements.txt).
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LOCUST_FILE = REPO / "benchmarks" / "load_test.py"
RESULTS_DIR = REPO / "benchmarks" / "results"
HOST = "127.0.0.1"
PORT = 8099
READY_URL = f"http://{HOST}:{PORT}/docs"
SERVER_STARTUP_TIMEOUT = 60


def _wait_for_server() -> None:
    import urllib.request
    import urllib.error

    deadline = time.monotonic() + SERVER_STARTUP_TIMEOUT
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(READY_URL, timeout=2)
            return
        except (urllib.error.URLError, OSError):
            time.sleep(0.5)
    raise RuntimeError(f"Server did not become ready within {SERVER_STARTUP_TIMEOUT}s")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--threads", type=int, default=50)
    parser.add_argument("--ramp", type=int, default=10)
    parser.add_argument("--run-time", default="30s")
    args = parser.parse_args()

    env = os.environ.copy()
    env.update({
        "LIBRAFLOW_STORAGE": "memory",
        "ENVIRONMENT": "development",
    })

    server_proc = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn",
            "libflow.api.app:app",
            "--host", HOST,
            "--port", str(PORT),
        ],
        cwd=str(REPO),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        print(f"[load-benchmark] starting server on {HOST}:{PORT}")
        _wait_for_server()
        print("[load-benchmark] server ready")

        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        csv_prefix = str(RESULTS_DIR / "load")

        locust_cmd = [
            sys.executable, "-m", "locust",
            "-f", str(LOCUST_FILE),
            "--host", f"http://{HOST}:{PORT}",
            "--headless",
            "-u", str(args.threads),
            "-r", str(args.ramp),
            "--run-time", args.run_time,
            "--csv", csv_prefix,
        ]
        print(f"[load-benchmark] running locust: {' '.join(locust_cmd)}")
        completed = subprocess.run(locust_cmd, cwd=str(REPO), capture_output=True, text=True)

        stats_path = Path(f"{csv_prefix}_stats.csv")
        failures_path = Path(f"{csv_prefix}_failures.csv")

        total_requests = 0
        total_failures = 0
        rps = 0.0
        if stats_path.exists():
            with open(stats_path, encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    if not row.get("Name"):
                        continue
                    total_requests += int(float(row.get("Request Count", 0) or 0))
                    total_failures += int(float(row.get("Failure Count", 0) or 0))
                    rps += float(row.get("Requests/s", 0.0) or 0.0)
        if failures_path.exists():
            with open(failures_path, encoding="utf-8") as f:
                total_failures = max(total_failures, len(list(csv.DictReader(f))))

        failure_rate = (total_failures / total_requests * 100) if total_requests else 100.0
        passed = failure_rate < 10.0 and total_requests > 0

        result = {
            "benchmark": "load-test",
            "run_at": datetime.now(timezone.utc).isoformat(),
            "parameters": {
                "threads": args.threads,
                "ramp": args.ramp,
                "run_time": args.run_time,
            },
            "total_requests": total_requests,
            "requests_per_second": round(rps, 2),
            "total_failures": total_failures,
            "failure_rate_pct": round(failure_rate, 2),
            "passed": passed,
            "locust_stdout_last_lines": (completed.stdout or "").splitlines()[-12:],
        }
        (RESULTS_DIR / "load_benchmark.json").write_text(
            json.dumps(result, indent=2), encoding="utf-8"
        )
        print(f"[load-benchmark] requests={total_requests} failures={total_failures} "
              f"rps={rps:.1f} failure_rate={failure_rate:.1f}% passed={passed}")
        return 0 if passed else 1
    finally:
        server_proc.terminate()
        try:
            server_proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server_proc.kill()
        print("[load-benchmark] server stopped")


if __name__ == "__main__":
    sys.exit(main())