"""PostgreSQL backup (pg_dump) and restore rehearsal — test databases only."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

ARTIFACTS = BACKEND_ROOT.parent / "artifacts" / "release"
RESULT_FILE = ARTIFACTS / "pg-backup-restore-rehearsal.json"

UNSAFE = ("prod", "production")
SAFE = ("test", "staging", "uat")


def _validate_url(url: str) -> None:
    if os.environ.get("ENABLE_LIVE_INTEGRATION_TESTS") != "true":
        raise SystemExit("ENABLE_LIVE_INTEGRATION_TESTS=true required")
    if os.environ.get("ALLOW_POSTGRES_TEST_DATABASE") != "true":
        raise SystemExit("ALLOW_POSTGRES_TEST_DATABASE=true required")
    parsed = urlparse(url)
    path = (parsed.path or "").lower()
    host = (parsed.hostname or "").lower()
    blob = f"{host}{path}"
    if any(u in blob for u in UNSAFE) and not any(s in blob for s in SAFE):
        raise SystemExit("Refusing backup/restore: database URL does not appear to be a test/staging database.")


def main() -> int:
    source_url = os.environ.get("TEST_POSTGRES_URL") or os.environ.get("TEST_POSTGRES_SOURCE_URL")
    restore_url = os.environ.get("TEST_POSTGRES_RESTORE_URL")
    if not source_url or not restore_url:
        print("NOT_CONFIGURED: TEST_POSTGRES_URL + TEST_POSTGRES_RESTORE_URL required")
        print("Use separate source and restore test database URLs. Never overwrite source.")
        return 1
    _validate_url(source_url)
    _validate_url(restore_url)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dump_path = Path(tempfile.gettempdir()) / f"vms-pg-uat-{stamp}.dump"
    result: dict = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "source_db_host": urlparse(source_url).hostname,
        "restore_db_host": urlparse(restore_url).hostname,
        "dump_file": str(dump_path),
        "status": "FAIL",
    }

    try:
        subprocess.run(
            ["pg_dump", "--format=custom", "--no-password", f"--file={dump_path}", source_url],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["pg_restore", "--clean", "--if-exists", "--no-password", f"--dbname={restore_url}", str(dump_path)],
            check=True,
            capture_output=True,
        )
        from alembic import command
        from alembic.config import Config
        from sqlalchemy import create_engine, text

        cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
        cfg.set_main_option("sqlalchemy.url", restore_url)
        command.upgrade(cfg, "head")
        engine = create_engine(restore_url, pool_pre_ping=True)
        with engine.connect() as conn:
            row = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            visitors = conn.execute(text("SELECT COUNT(*) FROM visitors")).scalar_one()
            visits = conn.execute(text("SELECT COUNT(*) FROM visits")).scalar_one()
            audits = conn.execute(text("SELECT COUNT(*) FROM audit_events")).scalar_one()
        engine.dispose()
        result.update({
            "status": "PASS",
            "alembic_revision": row,
            "visitor_count": visitors,
            "visit_count": visits,
            "audit_event_count": audits,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        })
        from app.application.release_evidence import record_live_result
        from app.domain.release_status import IntegrationReleaseStatus

        record_live_result("postgresql_backup_restore", IntegrationReleaseStatus.LIVE_VALIDATED, "pg_dump_restore=PASS")
        print(json.dumps(result, indent=2))
        ARTIFACTS.mkdir(parents=True, exist_ok=True)
        RESULT_FILE.write_text(json.dumps(result, indent=2), encoding="utf-8")
        return 0
    except FileNotFoundError:
        print("BLOCKED: pg_dump/pg_restore not available on this host")
        result["detail"] = "pg_dump/pg_restore not installed"
        ARTIFACTS.mkdir(parents=True, exist_ok=True)
        RESULT_FILE.write_text(json.dumps(result, indent=2), encoding="utf-8")
        return 1
    except subprocess.CalledProcessError as exc:
        result["detail"] = (exc.stderr or b"").decode("utf-8", errors="replace")[-500:]
        ARTIFACTS.mkdir(parents=True, exist_ok=True)
        RESULT_FILE.write_text(json.dumps(result, indent=2), encoding="utf-8")
        return 1
    finally:
        if dump_path.exists():
            dump_path.unlink()


if __name__ == "__main__":
    sys.exit(main())
