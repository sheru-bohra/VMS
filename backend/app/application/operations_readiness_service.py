"""Operations and deployment readiness aggregation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.application.scheduler_cycle_runner import ALL_SCHEDULER_LEASES
from app.application.scheduler_lease_service import SchedulerLeaseService
from app.application.security_readiness_service import evaluate_readiness
from app.core.config import settings
from app.core.runtime_instance import get_runtime_instance_id, masked_runtime_instance_id
from app.core.runtime_readiness import get_audit_cache, get_schema_cache
from app.domain.enums import BadgePrintJobStatus, NotificationStatus, PhysicalAccessStatus
from app.domain.models import BadgePrintJob, DataRetentionRun, Notification, VisitorAccessCredential
from app.infrastructure.database import database_dialect, engine
from app.infrastructure.database_schema import get_revision_display_name


def _backlog_level(count: int, attention: int, critical: int) -> str:
    if count >= critical:
        return "CRITICAL"
    if count >= attention:
        return "ATTENTION"
    return "HEALTHY"


def _postgres_validation_label() -> str:
    if database_dialect == "sqlite":
        return "DEVELOPMENT"
    if database_dialect == "postgresql":
        return "COMPATIBILITY_TESTED"
    return "NOT_VALIDATED"


def _pool_status() -> Dict[str, Any]:
    pool = engine.pool
    status: Dict[str, Any] = {"healthy": True, "state": "HEALTHY"}
    try:
        if hasattr(pool, "size"):
            status["pool_size"] = pool.size()
        if hasattr(pool, "checkedout"):
            checked = pool.checkedout()
            status["pool_in_use"] = checked
            pool_size = status.get("pool_size")
            if pool_size and checked >= pool_size + getattr(pool, "_max_overflow", 0):
                status["healthy"] = False
                status["state"] = "DATABASE_POOL_EXHAUSTED"
    except Exception:
        status["state"] = "UNKNOWN"
    return status


def get_database_status() -> Dict[str, Any]:
    schema = get_schema_cache()
    dialect_label = "SQLite" if database_dialect == "sqlite" else database_dialect.upper()
    env_label = "DEVELOPMENT" if database_dialect == "sqlite" else "PRODUCTION"
    revision = schema.get("current_revision")
    display = get_revision_display_name(revision) if revision else None
    pool = _pool_status()
    return {
        "dialect": dialect_label,
        "environment_label": env_label,
        "connected": True,
        "schema_revision": revision,
        "schema_revision_display": display,
        "schema_current": schema.get("schema_current", False),
        "postgres_validation": _postgres_validation_label(),
        "pool_size": pool.get("pool_size"),
        "pool_in_use": pool.get("pool_in_use"),
        "pool_state": pool.get("state"),
        "pool_healthy": pool.get("healthy", True),
    }


def get_scheduler_status(db: Session) -> List[Dict[str, Any]]:
    lease_svc = SchedulerLeaseService(db)
    now = datetime.now(timezone.utc)
    rows: List[Dict[str, Any]] = []
    for lease_name in ALL_SCHEDULER_LEASES:
        status = lease_svc.get_lease_status(lease_name)
        if status:
            rows.append({
                "scheduler": lease_name,
                "lease_state": status["state"],
                "lease_expires_at": status["lease_expires_at"],
                "last_success_at": status["last_success_at"],
                "last_error_code": status["last_error_code"],
                "owner_masked": status["owner_masked"],
            })
        else:
            rows.append({
                "scheduler": lease_name,
                "lease_state": "STANDBY",
                "lease_expires_at": None,
                "last_success_at": None,
                "last_error_code": None,
                "owner_masked": None,
            })
    return rows


def get_queue_status(db: Session) -> Dict[str, Any]:
    notif_pending = (
        db.query(func.count(Notification.id))
        .filter(Notification.status.in_([NotificationStatus.PENDING.value, NotificationStatus.PROCESSING.value]))
        .scalar()
        or 0
    )
    notif_failed = (
        db.query(func.count(Notification.id))
        .filter(Notification.status == NotificationStatus.FAILED.value)
        .scalar()
        or 0
    )
    provision_pending = (
        db.query(func.count(VisitorAccessCredential.id))
        .filter(VisitorAccessCredential.status == PhysicalAccessStatus.PENDING.value)
        .scalar()
        or 0
    )
    revocation_pending = (
        db.query(func.count(VisitorAccessCredential.id))
        .filter(VisitorAccessCredential.status == PhysicalAccessStatus.REVOCATION_PENDING.value)
        .scalar()
        or 0
    )
    print_pending = (
        db.query(func.count(BadgePrintJob.id))
        .filter(BadgePrintJob.status.in_([BadgePrintJobStatus.QUEUED.value, BadgePrintJobStatus.PROCESSING.value]))
        .scalar()
        or 0
    )
    print_failed = (
        db.query(func.count(BadgePrintJob.id))
        .filter(BadgePrintJob.status == BadgePrintJobStatus.FAILED.value)
        .scalar()
        or 0
    )
    last_retention = db.query(func.max(DataRetentionRun.created_at)).scalar()
    physical_total = provision_pending + revocation_pending + print_pending
    return {
        "notifications_pending": notif_pending,
        "notifications_failed": notif_failed,
        "notifications_backlog_level": _backlog_level(
            notif_pending,
            settings.notification_backlog_attention,
            settings.notification_backlog_critical,
        ),
        "access_provisioning_pending": provision_pending,
        "access_revocations_pending": revocation_pending,
        "badge_print_pending": print_pending,
        "badge_print_failed": print_failed,
        "physical_queue_backlog_level": _backlog_level(
            physical_total,
            settings.physical_queue_attention,
            settings.physical_queue_critical,
        ),
        "retention_last_run_at": last_retention.isoformat() if last_retention else None,
    }


def build_operations_readiness(db: Session) -> Dict[str, Any]:
    security = evaluate_readiness(db)
    audit = get_audit_cache()
    return {
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "runtime_instance_id": masked_runtime_instance_id(),
        "production_readiness": {
            "environment": settings.app_env,
            "ready": security.get("ready", False),
        },
        "database": get_database_status(),
        "schedulers": get_scheduler_status(db),
        "queues": get_queue_status(db),
        "integrations": security.get("checks", []),
        "audit_integrity": {
            "status": audit.get("status", "UNCONFIGURED"),
            "verified_at": audit.get("verified_at"),
            "sealed_count": audit.get("sealed_count", 0),
        },
        "security": {
            "auth_mode": settings.auth_mode,
            "rate_limit_backend": settings.rate_limit_backend,
            "log_format": settings.log_format,
        },
    }
