"""Centralized physical integration attention classification."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session, joinedload

from app.application.auth_service import AuthContext
from app.application.site_scope_service import can_access_location
from app.domain.enums import BadgePrintJobStatus, PhysicalAccessStatus, VisitStatus
from app.domain.models import BadgePrintJob, BadgePrinter, Visit, VisitorAccessCredential


SEVERITY_INFORMATION = "INFORMATION"
SEVERITY_ATTENTION = "ATTENTION"
SEVERITY_URGENT = "URGENT"

REASON_PROVISION_FAILED = "PROVISION_FAILED"
REASON_MANUAL_ACCESS_REQUIRED = "MANUAL_ACCESS_REQUIRED"
REASON_REVOCATION_PENDING = "REVOCATION_PENDING"
REASON_CHECKED_OUT_ACCESS_ACTIVE = "CHECKED_OUT_ACCESS_ACTIVE"
REASON_PRINT_FAILED = "PRINT_FAILED"
REASON_PRINTER_UNAVAILABLE = "PRINTER_UNAVAILABLE"

ACTION_RETRY_PROVISION = "RETRY_PROVISION"
ACTION_RETRY_REVOCATION = "RETRY_REVOCATION"
ACTION_RETRY_PRINT = "RETRY_PRINT"
ACTION_MANUAL_PRINT = "MANUAL_PRINT"


def _attention_for_credential(db: Session, cred: VisitorAccessCredential, visit: Optional[Visit]) -> Optional[Dict[str, Any]]:
    visit_status = visit.status if visit else None
    if visit_status == VisitStatus.CHECKED_OUT.value and cred.status == PhysicalAccessStatus.ACTIVE.value:
        return {
            "entity_type": "visitor_access_credential",
            "entity_id": cred.id,
            "credential_id": cred.id,
            "visit_id": cred.visit_id,
            "location_id": cred.location_id,
            "severity": SEVERITY_URGENT,
            "reason_code": REASON_CHECKED_OUT_ACCESS_ACTIVE,
            "status": cred.status,
            "visit_status": visit_status,
            "valid_until": cred.valid_until.isoformat() if cred.valid_until else None,
            "last_error_code": cred.last_error_code,
            "recommended_action": ACTION_RETRY_REVOCATION,
            "title": "Access still active after visitor checkout",
            "message": "Revocation is required.",
        }
    if cred.status == PhysicalAccessStatus.FAILED.value:
        return {
            "entity_type": "visitor_access_credential",
            "entity_id": cred.id,
            "credential_id": cred.id,
            "visit_id": cred.visit_id,
            "location_id": cred.location_id,
            "severity": SEVERITY_ATTENTION,
            "reason_code": REASON_PROVISION_FAILED,
            "status": cred.status,
            "visit_status": visit_status,
            "valid_until": cred.valid_until.isoformat() if cred.valid_until else None,
            "last_error_code": cred.last_error_code,
            "recommended_action": ACTION_RETRY_PROVISION,
            "title": "Access provisioning failed",
            "message": cred.last_error_code or "Provisioning failed.",
        }
    if cred.status == PhysicalAccessStatus.MANUAL_ACTION_REQUIRED.value:
        return {
            "entity_type": "visitor_access_credential",
            "entity_id": cred.id,
            "credential_id": cred.id,
            "visit_id": cred.visit_id,
            "location_id": cred.location_id,
            "severity": SEVERITY_ATTENTION,
            "reason_code": REASON_MANUAL_ACCESS_REQUIRED,
            "status": cred.status,
            "visit_status": visit_status,
            "valid_until": cred.valid_until.isoformat() if cred.valid_until else None,
            "last_error_code": cred.last_error_code,
            "recommended_action": ACTION_RETRY_PROVISION,
            "title": "Physical access requires manual action",
            "message": cred.last_error_code or "Manual action required.",
        }
    if cred.status == PhysicalAccessStatus.REVOCATION_PENDING.value:
        severity = SEVERITY_URGENT if visit_status == VisitStatus.CHECKED_OUT.value else SEVERITY_ATTENTION
        return {
            "entity_type": "visitor_access_credential",
            "entity_id": cred.id,
            "credential_id": cred.id,
            "visit_id": cred.visit_id,
            "location_id": cred.location_id,
            "severity": severity,
            "reason_code": REASON_REVOCATION_PENDING,
            "status": cred.status,
            "visit_status": visit_status,
            "valid_until": cred.valid_until.isoformat() if cred.valid_until else None,
            "last_error_code": cred.last_error_code,
            "recommended_action": ACTION_RETRY_REVOCATION,
            "title": "Access revocation pending",
            "message": cred.last_error_code or "Revocation pending.",
        }
    return None


def _attention_for_print_job(db: Session, job: BadgePrintJob) -> Optional[Dict[str, Any]]:
    if job.status == BadgePrintJobStatus.FAILED.value:
        reason = REASON_PRINT_FAILED
        if job.last_error_code in ("PRINTER_OFFLINE", "PRINTER_UNAVAILABLE", "MOCK_OFFLINE"):
            reason = REASON_PRINTER_UNAVAILABLE
        return {
            "entity_type": "badge_print_job",
            "entity_id": job.id,
            "print_job_id": job.id,
            "visit_id": job.visit_id,
            "location_id": job.location_id,
            "severity": SEVERITY_ATTENTION,
            "reason_code": reason,
            "status": job.status,
            "last_error_code": job.last_error_code,
            "recommended_action": ACTION_RETRY_PRINT,
            "title": "Badge print failed",
            "message": job.last_error_code or "Print failed.",
        }
    if job.status == BadgePrintJobStatus.MANUAL_ACTION_REQUIRED.value:
        reason = REASON_PRINT_FAILED
        if job.last_error_code in ("PRINTER_INACTIVE", "PRINTER_OFFLINE", "no_printer"):
            reason = REASON_PRINTER_UNAVAILABLE
        return {
            "entity_type": "badge_print_job",
            "entity_id": job.id,
            "print_job_id": job.id,
            "visit_id": job.visit_id,
            "location_id": job.location_id,
            "severity": SEVERITY_ATTENTION,
            "reason_code": reason,
            "status": job.status,
            "last_error_code": job.last_error_code,
            "recommended_action": ACTION_MANUAL_PRINT,
            "title": "Badge print requires manual action",
            "message": job.last_error_code or "Manual print action required.",
        }
    return None


def list_attention_items(db: Session, ctx: AuthContext) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    credentials = (
        db.query(VisitorAccessCredential)
        .order_by(VisitorAccessCredential.updated_at.desc())
        .limit(500)
        .all()
    )
    for cred in credentials:
        if not can_access_location(ctx, cred.location_id):
            continue
        visit = db.query(Visit).filter(Visit.id == cred.visit_id).first()
        item = _attention_for_credential(db, cred, visit)
        if item:
            visitor_name = ""
            location_name = ""
            if visit:
                if visit.visitor:
                    visitor_name = visit.visitor.full_name or ""
                if visit.location:
                    location_name = visit.location.name or ""
            item["visitor_name"] = visitor_name
            item["location_name"] = location_name
            item["checked_out_at"] = visit.checked_out_at.isoformat() if visit and visit.checked_out_at else None
            items.append(item)

    jobs = (
        db.query(BadgePrintJob)
        .order_by(BadgePrintJob.queued_at.desc())
        .limit(200)
        .all()
    )
    for job in jobs:
        if not can_access_location(ctx, job.location_id):
            continue
        item = _attention_for_print_job(db, job)
        if item:
            visit = (
                db.query(Visit)
                .options(joinedload(Visit.visitor), joinedload(Visit.location))
                .filter(Visit.id == job.visit_id)
                .first()
            )
            item["visitor_name"] = visit.visitor.full_name if visit and visit.visitor else ""
            item["location_name"] = visit.location.name if visit and visit.location else ""
            items.append(item)

    severity_rank = {SEVERITY_URGENT: 0, SEVERITY_ATTENTION: 1, SEVERITY_INFORMATION: 2}
    items.sort(key=lambda x: severity_rank.get(x.get("severity", SEVERITY_INFORMATION), 9))
    return items
