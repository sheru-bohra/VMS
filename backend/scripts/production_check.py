"""Production configuration validation (no deploy, no secret values printed)."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import text
from app.core.config import settings
from app.core.secret_validation import is_weak_secret
from app.infrastructure.database_engine import _dialect_from_url, build_engine, validate_production_database_policy
from app.infrastructure.database_schema import check_schema_at_head

FRONTEND_DIST = BACKEND_ROOT.parent / "frontend" / "dist"


def _line(label: str, status: str) -> None:
    print(f"{label:<28} {status}")


def main() -> int:
    print("Production Readiness")
    print("=" * 48)
    ok = True

    try:
        settings.validate_environment()
        _line("Configuration", "PASS")
    except Exception as exc:
        ok = False
        _line("Configuration", f"FAIL ({exc})")

    url = settings.resolved_database_url()
    dialect = _dialect_from_url(url)
    _line("Database Dialect", dialect.upper())

    try:
        validate_production_database_policy(url)
        engine, _ = build_engine(url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        _line("Database Connectivity", "PASS")
        try:
            info = check_schema_at_head(engine, require_version=True)
            if info.get("schema_current"):
                _line("Schema Revision", "CURRENT")
            else:
                ok = False
                _line("Schema Revision", "OUTDATED")
        except Exception as exc:
            ok = False
            _line("Schema Revision", f"FAIL ({getattr(exc, 'code', 'ERROR')})")
        engine.dispose()
    except Exception as exc:
        ok = False
        _line("Database Connectivity", f"FAIL ({type(exc).__name__})")

    sec_ok = (
        not settings.db_sql_echo
        and bool(settings.audit_integrity_key)
        and not is_weak_secret(settings.audit_integrity_key or "", 32)
        and bool(settings.document_encryption_key)
    )
    _line("Security Configuration", "PASS" if sec_ok else "FAIL")
    if not sec_ok:
        ok = False

    _line("Audit Integrity Config", "PASS" if settings.audit_integrity_key else "FAIL")
    _line("Rate Limiter", "PASS" if settings.rate_limit_backend == "database" else "FAIL")
    _line("Authentication", "CONFIGURED" if settings.auth_mode == "entra" and settings.entra_client_id else "FAIL")
    _line("Email", "CONFIGURED" if settings.email_provider == "dev_outbox" else "CHECK")
    _line(
        "File Scanner",
        "CONFIGURED" if settings.file_scanner_provider == "clamav" else settings.file_scanner_provider,
    )
    ac = "DISABLED"
    if settings.access_control_enabled:
        ac = "CONFIGURED" if settings.access_control_provider != "dev_mock" else "FAIL"
    _line("Access Control", ac)
    bp = "DISABLED"
    if settings.badge_printer_enabled:
        bp = "CONFIGURED" if settings.badge_printer_provider != "dev_mock" else "FAIL"
    _line("Badge Printer", bp)

    if FRONTEND_DIST.exists():
        _line("Frontend Build", "PASS")
    else:
        _line("Frontend Build", "NOT_BUILT (run npm run build)")

    print("=" * 48)
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
