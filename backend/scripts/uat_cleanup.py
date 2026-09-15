"""Remove synthetic UAT fixtures. Never deletes audit events."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.application.uat_data_service import cleanup_uat_synthetic_data
from app.infrastructure.database import SessionLocal


def main() -> int:
    db = SessionLocal()
    try:
        result = cleanup_uat_synthetic_data(db)
        print(f"UAT cleanup complete: {result}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
