"""Production security readiness evaluation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.application.audit_integrity_service import verify_chain
from app.core.config import settings
from app.core.secret_validation import is_weak_secret


def _status_label(configured: bool, mock_only: bool = False, live: bool = False) -> str:
    if live:
        return "LIVE_VALIDATED"
    if mock_only:
        return "MOCK_TESTED"
    if configured:
        return "CONFIGURED"
    return "NOT_CONFIGURED"


def evaluate_readiness(db: Session) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []
    is_prod = settings.is_production

    entra_ok = bool(settings.entra_tenant_id and settings.entra_client_id)
    checks.append({
        "key": "authentication",
        "label": "Microsoft Entra ID",
        "status": _status_label(entra_ok, mock_only=not is_prod and entra_ok),
    })

    graph_ok = bool(
        settings.graph_tenant_id and settings.graph_client_id and settings.graph_client_secret and settings.graph_sender_mailbox
    )
    email_dev = settings.email_provider == "dev_outbox"
    checks.append({
        "key": "email",
        "label": "Email Provider",
        "status": "DEVELOPMENT_ONLY" if email_dev else _status_label(graph_ok, mock_only=True),
        "detail": settings.email_provider,
    })

    audit_result = verify_chain(db)
    checks.append({
        "key": "audit_integrity",
        "label": "Audit Integrity",
        "status": audit_result.get("status", "UNCONFIGURED"),
        "detail": f"Sealed: {audit_result.get('sealed_count', 0)}",
    })

    enc_ok = bool(settings.document_encryption_key) and not is_weak_secret(settings.document_encryption_key, 32)
    checks.append({
        "key": "document_encryption",
        "label": "Document Encryption",
        "status": _status_label(enc_ok) if is_prod else ("CONFIGURED" if enc_ok else "DEVELOPMENT_ONLY"),
    })

    scanner = settings.file_scanner_provider
    checks.append({
        "key": "file_scanner",
        "label": "Malware Scanner",
        "status": "DEVELOPMENT_ONLY" if scanner == "dev_noop" else _status_label(scanner == "clamav", mock_only=True),
        "detail": scanner,
    })

    rl_backend = settings.rate_limit_backend
    checks.append({
        "key": "rate_limiting",
        "label": "Rate Limit Backend",
        "status": "CONFIGURED" if rl_backend == "database" else "DEVELOPMENT_ONLY",
        "detail": rl_backend,
    })

    https_ok = settings.public_app_base_url.startswith("https://")
    cors_list = settings.cors_origin_list
    cors_wildcard = any(o == "*" for o in cors_list)
    checks.append({
        "key": "public_url",
        "label": "Public HTTPS URL",
        "status": "CONFIGURED" if https_ok else "DEVELOPMENT_ONLY",
    })
    checks.append({
        "key": "cors",
        "label": "CORS Origins",
        "status": "CONFIGURED" if cors_list and not cors_wildcard else ("NOT_CONFIGURED" if is_prod else "DEVELOPMENT_ONLY"),
    })

    ac_enabled = settings.access_control_enabled
    ac_provider = settings.access_control_provider
    checks.append({
        "key": "access_control",
        "label": "Access Control Provider",
        "status": (
            "DEVELOPMENT_ONLY" if ac_provider == "dev_mock"
            else ("CONFIGURED" if ac_enabled and ac_provider != "disabled" else "DISABLED")
        ),
        "detail": ac_provider if ac_enabled else "disabled",
    })

    bp_enabled = settings.badge_printer_enabled
    bp_provider = settings.badge_printer_provider
    checks.append({
        "key": "badge_printer",
        "label": "Badge Printer Provider",
        "status": (
            "DEVELOPMENT_ONLY" if bp_provider == "dev_mock"
            else ("CONFIGURED" if bp_enabled and bp_provider != "disabled" else "DISABLED")
        ),
        "detail": bp_provider if bp_enabled else "disabled",
    })

    ready = True
    if is_prod:
        for c in checks:
            if c["status"] in ("NOT_CONFIGURED", "DEVELOPMENT_ONLY", "BROKEN", "UNCONFIGURED"):
                if c["key"] not in ("file_scanner"):  # scanner may be mock-tested
                    ready = False

    return {
        "ready": ready,
        "environment": settings.app_env,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
    }
