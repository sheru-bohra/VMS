"""Development-only manual UAT seed and cleanup."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy.orm import sessionmaker

from app.application.bootstrap import bootstrap_development_data
from app.application.uat_data_service import cleanup_uat_synthetic_data, seed_uat_synthetic_visitors
from app.core.config import settings
from app.infrastructure.database_engine import create_database_engine


def _session():
    engine = create_database_engine(settings.resolved_database_url())
    Session = sessionmaker(bind=engine)
    return Session()


def seed() -> int:
    if settings.is_production:
        print("Refusing to seed manual UAT data when APP_ENV=production.")
        return 1
    db = _session()
    try:
        bootstrap_development_data(db)
        created = seed_uat_synthetic_visitors(db)
        print(f"Manual UAT seed complete. Synthetic visitors created: {created}")
        return 0
    finally:
        db.close()


def cleanup() -> int:
    if settings.is_production:
        print("Refusing to cleanup manual UAT data when APP_ENV=production.")
        return 1
    db = _session()
    try:
        result = cleanup_uat_synthetic_data(db)
        print(f"Manual UAT cleanup complete: {result}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "seed"
    if cmd == "cleanup":
        sys.exit(cleanup())
    sys.exit(seed())
