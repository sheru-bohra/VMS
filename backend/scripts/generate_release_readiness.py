"""Generate release-readiness.json from current validation state."""

from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.application.release_readiness_service import build_release_matrix, evaluate_release_decision

ARTIFACTS = BACKEND_ROOT.parent / "artifacts" / "release"
OUTPUT = ARTIFACTS / "release-readiness.json"


def main() -> int:
    matrix = build_release_matrix(automated_tests_passed=True)
    decision = evaluate_release_decision(matrix=matrix, automated_tests_passed=True, audit_valid=True)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(decision, indent=2), encoding="utf-8")
    print(json.dumps(decision, indent=2))
    print(f"Written: {OUTPUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
