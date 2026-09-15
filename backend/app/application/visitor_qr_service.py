"""Visitor invitation QR verification for reception/security."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session, joinedload

from app.application.auth_service import AuthContext
from app.application.invitation_service import _invitation_status, _load_by_token
from app.application.site_scope_service import can_access_location
from app.domain.enums import Permission, SecurityClearanceStatus, VisitSource, VisitStatus, role_has_permission
from app.domain.models import Visit, Visitor


class QrVerifyError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _require_verify(ctx: AuthContext) -> None:
    if not role_has_permission(ctx.role, Permission.VISITOR_QR_VERIFY):
        raise QrVerifyError("forbidden", "Permission denied.", 403)


def _build_verify_result(
    visit: Visit,
    inv_status: str,
    can_operate: bool,
    message: Optional[str] = None,
    security_status: Optional[str] = None,
) -> Dict[str, Any]:
    visitor = visit.visitor
    visitor_type_name = visitor.visitor_type.name if visitor and visitor.visitor_type else None
    location = visit.location
    sec = security_status or visit.security_clearance_status or SecurityClearanceStatus.CLEAR.value
    return {
        "valid": can_operate,
        "code": "VALID" if can_operate else inv_status,
        "message": message,
        "visit_id": visit.id,
        "registration_reference": visit.registration_reference,
        "status": visit.status,
        "source": visit.source,
        "visitor_name": visitor.full_name if visitor else "",
        "company": visitor.company if visitor else None,
        "visitor_type": visitor_type_name,
        "visitor_mobile": visitor.phone if visitor else None,
        "host_name": visit.host_name,
        "site_name": location.name if location else "",
        "site_id": visit.location_id,
        "purpose": visit.purpose,
        "scheduled_start": visit.scheduled_start.isoformat() if visit.scheduled_start else None,
        "scheduled_end": visit.scheduled_end.isoformat() if visit.scheduled_end else None,
        "arrived_at": visit.arrived_at.isoformat() if visit.arrived_at else None,
        "checked_in_at": visit.checked_in_at.isoformat() if visit.checked_in_at else None,
        "invitation_status": inv_status,
        "security_status": sec,
        "can_mark_arrived": can_operate and visit.status == VisitStatus.APPROVED.value,
        "can_check_in": can_operate and visit.status == VisitStatus.ARRIVED.value,
        "can_check_out": can_operate and visit.status == VisitStatus.ONSITE.value,
    }


def verify_by_token(db: Session, ctx: AuthContext, token: str) -> Dict[str, Any]:
    _require_verify(ctx)

    visit = _load_by_token(db, token)
    if not visit:
        raise QrVerifyError("INVALID_QR", "Invalid visitor QR code.", 404)

    if not can_access_location(ctx, visit.location_id):
        raise QrVerifyError("LOCATION_ACCESS_DENIED", "You do not have access to visitors at this location.", 403)

    return _evaluate_visit(db, ctx, visit, audit_token_present=True)


def verify_by_reference(db: Session, ctx: AuthContext, reference: str) -> Dict[str, Any]:
    _require_verify(ctx)

    ref = reference.strip().upper()
    visit = (
        db.query(Visit)
        .options(
            joinedload(Visit.visitor).joinedload(Visitor.visitor_type),
            joinedload(Visit.location),
        )
        .filter(Visit.registration_reference == ref)
        .first()
    )
    if not visit:
        raise QrVerifyError("VISIT_NOT_FOUND", "No visit found for this reference.", 404)

    if not can_access_location(ctx, visit.location_id):
        raise QrVerifyError("LOCATION_ACCESS_DENIED", "You do not have access to visitors at this location.", 403)

    return _evaluate_visit(db, ctx, visit, audit_token_present=False)


def _evaluate_visit(db: Session, ctx: AuthContext, visit: Visit, audit_token_present: bool) -> Dict[str, Any]:
    if visit.status == VisitStatus.REJECTED.value:
        return _build_verify_result(visit, "REJECTED", False, "This visitor request was not approved.")

    if visit.status == VisitStatus.CANCELLED.value:
        return _build_verify_result(visit, "CANCELLED", False, "This visitor invitation is no longer active.")

    if visit.status == VisitStatus.CHECKED_OUT.value:
        return _build_verify_result(visit, "CHECKED_OUT", False, "This visitor has already checked out.")

    inv_status = "ACTIVE"
    if visit.source == VisitSource.ADVANCE_REGISTRATION.value:
        inv_status = _invitation_status(visit)
        if inv_status == "EXPIRED":
            return _build_verify_result(visit, "EXPIRED", False, "This invitation has expired.")
        if inv_status == "NOT_YET_VALID":
            return _build_verify_result(visit, "NOT_YET_VALID", False, "This invitation is not yet valid.")
        if inv_status in ("INVALID", "NOT_ACTIVE", "PENDING_APPROVAL"):
            return _build_verify_result(visit, inv_status, False, "This visitor invitation is not active.")

    if visit.status == VisitStatus.PENDING_APPROVAL.value:
        return _build_verify_result(visit, "PENDING_APPROVAL", False, "This visit is awaiting approval.")

    from app.application.security_screening_service import screen_visit, get_latest_screening
    screen_visit(db, visit.id, trigger="qr_verify")
    db.refresh(visit)

    from app.application.compliance_service import evaluate_visit_compliance
    from app.domain.enums import ComplianceStatus
    evaluate_visit_compliance(db, visit.id, trigger="qr_verify")
    db.refresh(visit)

    if visit.compliance_status == ComplianceStatus.NON_COMPLIANT.value:
        return _build_verify_result(
            visit, "COMPLIANCE_NON_COMPLIANT", False,
            "Access blocked: compliance requirements are not satisfied.",
            security_status=visit.security_clearance_status,
        )
    if visit.compliance_status == ComplianceStatus.REVIEW_REQUIRED.value:
        return _build_verify_result(
            visit, "COMPLIANCE_REVIEW", False,
            "Compliance review required before visitor operations can continue.",
            security_status=visit.security_clearance_status,
        )

    if visit.security_clearance_status == SecurityClearanceStatus.BLOCKED.value:
        return _build_verify_result(
            visit, "SECURITY_BLOCKED", False,
            "Access blocked by security screening.",
            security_status=visit.security_clearance_status,
        )
    if visit.security_clearance_status == SecurityClearanceStatus.REVIEW.value:
        latest = get_latest_screening(db, visit.id)
        if not latest or not latest.resolution:
            return _build_verify_result(
                visit, "SECURITY_REVIEW", False,
                "Security review required before visitor operations can continue.",
                security_status=visit.security_clearance_status,
            )

    from app.application.audit_service import AuditService
    audit = AuditService(db)
    audit.record(
        action="INVITATION_QR_VERIFIED",
        entity_type="visit",
        entity_id=str(visit.id),
        actor_id=ctx.user_id,
        actor_email=ctx.email,
        location_id=visit.location_id,
        after_value={"status": visit.status, "token_present": audit_token_present},
    )
    db.commit()

    return _build_verify_result(visit, inv_status, True)
