"""Release candidate orchestration — local checks only, no live external integrations."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Optional

BACKEND_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_ROOT.parent
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts" / "release"
READINESS_FILE = ARTIFACTS_DIR / "release-readiness.json"


def _run(cmd: list[str], cwd: Optional[Path] = None) -> tuple[bool, str]:
    result = subprocess.run(
        cmd,
        cwd=str(cwd or PROJECT_ROOT),
        capture_output=True,
        text=True,
    )
    output = (result.stdout or "") + (result.stderr or "")
    return result.returncode == 0, output


def main() -> int:
    sys.path.insert(0, str(BACKEND_ROOT))
    from app.application.release_readiness_service import build_release_matrix, evaluate_release_decision
    from app.core.config import settings

    checks: dict[str, bool] = {}
    print("VMS Release Candidate Check")
    print("=" * 48)
    print(f"Release version: {settings.app_release_version}")
    print()

    steps = [
        ("migrate_current", [sys.executable, "-m", "alembic", "current"], BACKEND_ROOT),
        ("perf_smoke", [sys.executable, "scripts/perf_smoke.py"], BACKEND_ROOT),
        ("production_check", [sys.executable, "scripts/production_check.py"], BACKEND_ROOT),
    ]
    npm_steps = [
        ("test_release", ["npm", "run", "test:release"]),
        ("npm_test", ["npm", "test"]),
        ("page_verify", ["npm", "run", "page:verify"]),
        ("audit_verify", ["npm", "run", "audit:verify"]),
        ("security_check", ["npm", "run", "security:check"]),
        ("build", ["npm", "run", "build"]),
        ("secret_scan", ["npm", "run", "frontend:secret-scan"]),
    ]

    for name, cmd, cwd in steps:
        ok, out = _run(cmd, cwd)
        checks[name] = ok
        print(f"{name:<22} {'PASS' if ok else 'FAIL'}")
        if not ok and out.strip():
            print(out.strip()[-500:])

    for name, cmd in npm_steps:
        ok, out = _run(cmd)
        checks[name] = ok
        print(f"{name:<22} {'PASS' if ok else 'FAIL'}")
        if not ok and out.strip():
            print(out.strip()[-800:])

    audit_valid = checks.get("audit_verify", False)
    tests_ok = checks.get("npm_test", False) and checks.get("test_release", False)
    build_ok = checks.get("build", False)
    security_ok = checks.get("security_check", False)

    matrix = build_release_matrix(automated_tests_passed=tests_ok)
    decision = evaluate_release_decision(
        matrix=matrix,
        automated_tests_passed=tests_ok,
        audit_valid=audit_valid,
        build_passed=build_ok,
        security_passed=security_ok,
    )
    decision["checks"] = checks
    decision["release_version"] = settings.app_release_version

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    READINESS_FILE.write_text(json.dumps(decision, indent=2), encoding="utf-8")

    print()
    print("Release matrix:")
    for k, v in matrix.items():
        print(f"  {k:<18} {v}")
    print()
    print(f"Decision: {decision['decision']}")
    if decision["blockers"]:
        for b in decision["blockers"]:
            print(f"  BLOCKER: {b}")
    if decision["conditions"]:
        for c in decision["conditions"]:
            print(f"  CONDITION: {c}")
    print(f"Artifact: {READINESS_FILE}")

    all_local = all(checks.values())
    if decision["decision"] == "NO_GO" or not all_local:
        print("=" * 48)
        print("RC CHECK: FAIL (see decision and checks)")
        return 1
    print("=" * 48)
    print("RC CHECK: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
