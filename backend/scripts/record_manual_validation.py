"""Record manual live validation evidence (Entra browser UAT, manual checklists)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.application.release_evidence import record_live_result
from app.domain.release_status import IntegrationReleaseStatus

VALID = {s.value for s in IntegrationReleaseStatus}
ARTIFACTS = BACKEND_ROOT.parent / "artifacts" / "release"
MANUAL_FILE = ARTIFACTS / "manual-uat-evidence.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Record manual live validation evidence")
    parser.add_argument("component", help="e.g. entra, graph_email, manual_uat_walk_in")
    parser.add_argument("status", choices=sorted(VALID))
    parser.add_argument("detail", nargs="?", default="", help="Safe evidence note (no secrets)")
    args = parser.parse_args()
    status = IntegrationReleaseStatus(args.status)
    record_live_result(args.component, status, args.detail or None)
    manual = {}
    if MANUAL_FILE.exists():
        manual = json.loads(MANUAL_FILE.read_text(encoding="utf-8"))
    manual[args.component] = {"status": args.status, "detail": args.detail}
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    MANUAL_FILE.write_text(json.dumps(manual, indent=2), encoding="utf-8")
    print(f"Recorded {args.component}={args.status}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
