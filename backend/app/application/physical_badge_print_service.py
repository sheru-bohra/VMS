"""Physical badge print job orchestration."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session, joinedload

from app.application.audit_service import AuditService
from app.application.auth_service import AuthContext
from app.application.badge_printer_provider import BadgePrintPayload, get_badge_printer_provider
from app.application.badge_service import BadgeError, _active_badge, _build_badge_dict, _load_visit, issue_badge
from app.application.site_scope_service import can_access_location
from app.core.config import settings
from app.core.provider_error_sanitizer import redact_sensitive_text, sanitize_badge_printer_error
from app.domain.enums import BadgePrintJobStatus, BadgeStatus, Permission, VisitStatus, role_has_permission
from app.domain.models import BadgePrintJob, BadgePrinter, Visit, VisitorBadge


logger = logging.getLogger(__name__)


class PhysicalBadgePrintError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _require_read(ctx: AuthContext) -> None:
    if not role_has_permission(ctx.role, Permission.BADGE_PRINTER_READ):
        raise PhysicalBadgePrintError("forbidden", "Permission denied.", 403)


def _require_operate(ctx: AuthContext) -> None:
    if not role_has_permission(ctx.role, Permission.BADGE_PRINTER_OPERATE):
        raise PhysicalBadgePrintError("forbidden", "Permission denied.", 403)


def get_default_printer(db: Session, location_id: int) -> Optional[BadgePrinter]:
    return (
        db.query(BadgePrinter)
        .filter(
            BadgePrinter.location_id == location_id,
            BadgePrinter.is_active.is_(True),
            BadgePrinter.is_default.is_(True),
        )
        .first()
    )


def _job_dict(db: Session, job: BadgePrintJob) -> Dict[str, Any]:
    visit = db.query(Visit).options(joinedload(Visit.visitor), joinedload(Visit.location)).filter(Visit.id == job.visit_id).first()
    badge = db.query(VisitorBadge).filter(VisitorBadge.id == job.visitor_badge_id).first()
    printer = db.query(BadgePrinter).filter(BadgePrinter.id == job.printer_id).first()
    return {
        "id": job.id,
        "visit_id": job.visit_id,
        "visitor_badge_id": job.visitor_badge_id,
        "badge_number": badge.badge_number if badge else None,
        "visitor_name": visit.visitor.full_name if visit and visit.visitor else "",
        "location_id": job.location_id,
        "location_name": visit.location.name if visit and visit.location else "",
        "printer_id": job.printer_id,
        "printer_name": printer.name if printer else None,
        "status": job.status,
        "attempt_count": job.attempt_count,
        "queued_at": job.queued_at.isoformat() if job.queued_at else None,
        "printed_at": job.printed_at.isoformat() if job.printed_at else None,
        "last_error_code": job.last_error_code,
    }


def request_physical_print(
    db: Session,
    ctx: AuthContext,
    visit_id: int,
    printer_id: Optional[int] = None,
    idempotency_key: Optional[str] = None,
) -> Dict[str, Any]:
    _require_operate(ctx)
    visit = _load_visit(db, visit_id)
    if not visit:
        raise PhysicalBadgePrintError("VISIT_NOT_FOUND", "Visit not found.", 404)
    if not can_access_location(ctx, visit.location_id):
        raise PhysicalBadgePrintError("forbidden", "Location access denied.", 403)
    if visit.status != VisitStatus.ONSITE.value:
        raise PhysicalBadgePrintError("INVALID_VISIT_STATE", "Visitor must be onsite.", 409)

    if not settings.badge_printer_enabled:
        raise PhysicalBadgePrintError("PRINTER_DISABLED", "Physical badge printing is not enabled.", 400)

    badge = _active_badge(visit)
    if not badge:
        try:
            badge_detail = issue_badge(db, ctx, visit_id)
            badge = db.query(VisitorBadge).filter(VisitorBadge.id == badge_detail["id"]).first()
        except BadgeError as exc:
            raise PhysicalBadgePrintError(exc.code, exc.message, exc.status_code)

    if badge.status != BadgeStatus.ACTIVE.value:
        raise PhysicalBadgePrintError("BADGE_EXPIRED", "Badge is not active.", 409)

    printer = None
    if printer_id:
        printer = db.query(BadgePrinter).filter(BadgePrinter.id == printer_id, BadgePrinter.is_active.is_(True)).first()
        if not printer or printer.location_id != visit.location_id:
            raise PhysicalBadgePrintError("invalid_printer", "Printer not found for this location.", 404)
    else:
        printer = get_default_printer(db, visit.location_id)
    if not printer:
        raise PhysicalBadgePrintError("no_printer", "No default printer configured for this location.", 400)

    dedupe = idempotency_key or f"print:{visit_id}:{badge.id}:{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}"
    existing = db.query(BadgePrintJob).filter(BadgePrintJob.idempotency_key == dedupe).first()
    if existing:
        return _job_dict(db, existing)

    job = BadgePrintJob(
        visitor_badge_id=badge.id,
        visit_id=visit_id,
        location_id=visit.location_id,
        printer_id=printer.id,
        status=BadgePrintJobStatus.QUEUED.value,
        requested_by_user_id=ctx.user_id,
        idempotency_key=dedupe,
    )
    db.add(job)
    db.flush()

    AuditService(db).record(
        action="BADGE_PRINT_REQUESTED",
        entity_type="badge_print_job",
        entity_id=str(job.id),
        actor_id=ctx.user_id,
        actor_email=ctx.email,
        location_id=visit.location_id,
        after_value={"badge_number": badge.badge_number},
    )

    db.flush()
    process_print_jobs(db, limit=5)
    db.refresh(job)
    return _job_dict(db, job)


def process_print_jobs(db: Session, limit: int = 20) -> int:
    if not settings.badge_printer_enabled:
        return 0
    jobs = (
        db.query(BadgePrintJob)
        .filter(BadgePrintJob.status == BadgePrintJobStatus.QUEUED.value)
        .order_by(BadgePrintJob.id.asc())
        .limit(limit)
        .all()
    )
    processed = 0
    for job in jobs:
        try:
            _process_single_job(db, job)
            processed += 1
        except Exception:
            job.status = BadgePrintJobStatus.FAILED.value
            job.failed_at = datetime.now(timezone.utc)
            job.last_error_code = "PROCESSING_ERROR"
        db.flush()
    return processed


def _process_single_job(db: Session, job: BadgePrintJob) -> None:
    badge = db.query(VisitorBadge).filter(VisitorBadge.id == job.visitor_badge_id).first()
    if not badge or badge.status != BadgeStatus.ACTIVE.value:
        job.status = BadgePrintJobStatus.CANCELLED.value
        job.last_error_code = "BADGE_NOT_ACTIVE"
        return

    visit = _load_visit(db, job.visit_id)
    if not visit:
        job.status = BadgePrintJobStatus.CANCELLED.value
        return

    printer = db.query(BadgePrinter).filter(BadgePrinter.id == job.printer_id).first()
    if not printer or not printer.is_active:
        job.status = BadgePrintJobStatus.MANUAL_ACTION_REQUIRED.value
        job.last_error_code = "PRINTER_INACTIVE"
        return

    job.status = BadgePrintJobStatus.PROCESSING.value
    job.started_at = datetime.now(timezone.utc)
    job.attempt_count += 1

    validity = badge.expires_at.isoformat() if badge.expires_at else None
    payload = BadgePrintPayload(
        badge_number=badge.badge_number,
        visitor_name=visit.visitor.full_name if visit.visitor else "",
        company=visit.visitor.company if visit.visitor else None,
        visitor_type=visit.visitor.visitor_type.name if visit.visitor and visit.visitor.visitor_type else None,
        host_name=visit.host_name,
        location_name=visit.location.name if visit.location else "",
        validity_text=validity,
    )

    provider = get_badge_printer_provider(printer.provider_key)
    result = provider.print_badge(
        printer.provider_external_printer_ref,
        payload,
        job.idempotency_key or f"job-{job.id}",
    )

    if result.success:
        job.status = BadgePrintJobStatus.PRINTED.value
        job.printed_at = datetime.now(timezone.utc)
        job.provider_job_reference = result.provider_job_reference
        badge.printed_at = job.printed_at
        badge.print_count = (badge.print_count or 0) + 1
        AuditService(db).record(
            action="BADGE_PRINTED_PHYSICAL",
            entity_type="badge_print_job",
            entity_id=str(job.id),
            actor_id=job.requested_by_user_id,
            location_id=job.location_id,
            after_value={"badge_number": badge.badge_number},
        )
    else:
        safe_code = sanitize_badge_printer_error(result.error_code)
        job.last_error_code = safe_code
        job.failed_at = datetime.now(timezone.utc)
        logger.warning(
            "Badge print failed job=%s visit=%s error=%s",
            job.id,
            job.visit_id,
            redact_sensitive_text(str(result.error_code or safe_code)),
        )
        if result.transient and job.attempt_count < settings.badge_print_max_attempts:
            job.status = BadgePrintJobStatus.QUEUED.value
        else:
            job.status = (
                BadgePrintJobStatus.MANUAL_ACTION_REQUIRED.value
                if not result.transient
                else BadgePrintJobStatus.FAILED.value
            )
        AuditService(db).record(
            action="BADGE_PRINT_FAILED",
            entity_type="badge_print_job",
            entity_id=str(job.id),
            location_id=job.location_id,
            after_value={"error_code": safe_code},
        )


def list_print_jobs(
    db: Session,
    ctx: AuthContext,
    attention_only: bool = False,
) -> List[Dict[str, Any]]:
    _require_read(ctx)
    q = db.query(BadgePrintJob).order_by(BadgePrintJob.queued_at.desc())
    if attention_only:
        q = q.filter(
            BadgePrintJob.status.in_([
                BadgePrintJobStatus.FAILED.value,
                BadgePrintJobStatus.MANUAL_ACTION_REQUIRED.value,
            ])
        )
    rows = q.limit(200).all()
    return [_job_dict(db, j) for j in rows if can_access_location(ctx, j.location_id)]


def retry_print_job(db: Session, ctx: AuthContext, job_id: int) -> Dict[str, Any]:
    _require_operate(ctx)
    job = db.query(BadgePrintJob).filter(BadgePrintJob.id == job_id).first()
    if not job:
        raise PhysicalBadgePrintError("not_found", "Print job not found.", 404)
    if not can_access_location(ctx, job.location_id):
        raise PhysicalBadgePrintError("forbidden", "Location access denied.", 403)
    if job.status not in (BadgePrintJobStatus.FAILED.value, BadgePrintJobStatus.MANUAL_ACTION_REQUIRED.value):
        raise PhysicalBadgePrintError("invalid_state", "Job is not retryable.", 409)
    job.status = BadgePrintJobStatus.QUEUED.value
    job.failed_at = None
    AuditService(db).record(
        action="BADGE_PRINT_RETRIED",
        entity_type="badge_print_job",
        entity_id=str(job.id),
        actor_id=ctx.user_id,
        actor_email=ctx.email,
        location_id=job.location_id,
    )
    db.flush()
    process_print_jobs(db, limit=5)
    db.refresh(job)
    return _job_dict(db, job)
