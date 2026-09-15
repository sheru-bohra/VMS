"""Performance smoke baseline for release candidate validation."""

from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from fastapi.testclient import TestClient

from app.main import create_app

ARTIFACTS_DIR = BACKEND_ROOT.parent / "artifacts" / "release"
OUTPUT_FILE = ARTIFACTS_DIR / "perf-smoke.json"

SCENARIOS = [
    ("health_live", "/api/health/live"),
    ("health_ready", "/api/health/ready"),
    ("health", "/api/health"),
]

CONCURRENCY_LEVELS = [10, 25, 50]
P95_TARGET_MS = {
    "health_live": 1000,
    "health": 1000,
    "health_ready": 1000,
}


def _measure(client: TestClient, path: str, iterations: int = 20) -> Dict[str, Any]:
    durations: List[float] = []
    errors = 0
    for _ in range(iterations):
        start = time.perf_counter()
        resp = client.get(path)
        elapsed_ms = (time.perf_counter() - start) * 1000
        durations.append(elapsed_ms)
        if resp.status_code >= 500:
            errors += 1
    durations_sorted = sorted(durations)
    p95_idx = max(0, int(len(durations_sorted) * 0.95) - 1)
    return {
        "requests": iterations,
        "success_rate": round((iterations - errors) / iterations, 4),
        "error_5xx": errors,
        "median_ms": round(statistics.median(durations), 2),
        "p95_ms": round(durations_sorted[p95_idx], 2),
        "max_ms": round(max(durations), 2),
        "target_p95_ms": P95_TARGET_MS.get(path.split("/")[-1].replace("health_", "health_"), 2000),
    }


def run_perf_smoke() -> Dict[str, Any]:
    app = create_app()
    results: Dict[str, Any] = {
        "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "scenarios": {},
        "concurrency": {},
        "unexpected_5xx": 0,
        "warnings": [],
    }
    with TestClient(app) as client:
        for name, path in SCENARIOS:
            row = _measure(client, path, iterations=25)
            results["scenarios"][name] = row
            results["unexpected_5xx"] += row["error_5xx"]
            target = P95_TARGET_MS.get(name, 2000)
            if row["p95_ms"] > target:
                results["warnings"].append(f"{name} p95 {row['p95_ms']}ms exceeds engineering target {target}ms")

        for level in CONCURRENCY_LEVELS:
            batch_start = time.perf_counter()
            errors = 0
            for _ in range(level):
                resp = client.get("/api/health/live")
                if resp.status_code >= 500:
                    errors += 1
            elapsed = (time.perf_counter() - batch_start) * 1000
            results["concurrency"][str(level)] = {
                "requests": level,
                "total_ms": round(elapsed, 2),
                "error_5xx": errors,
            }
            results["unexpected_5xx"] += errors

    results["passed"] = results["unexpected_5xx"] == 0
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(results, indent=2), encoding="utf-8")
    return results


def main() -> int:
    print("VMS Performance Smoke")
    print("=" * 48)
    results = run_perf_smoke()
    for name, row in results["scenarios"].items():
        print(f"{name:<20} p95={row['p95_ms']}ms 5xx={row['error_5xx']}")
    print(f"Unexpected 5xx total: {results['unexpected_5xx']}")
    if results["warnings"]:
        for w in results["warnings"]:
            print(f"WARNING: {w}")
    print(f"Artifact: {OUTPUT_FILE}")
    print("PASS" if results["passed"] else "FAIL")
    return 0 if results["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
