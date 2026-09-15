"""Approval workflow service."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import or_, update
from sqlalchemy.orm import Session, joinedload

from app.application.audit_service import AuditService
from app.application.auth_service import AuthContext
from app.application.approval_actor import ApprovalActor, actor_from_auth
from app.application.site_scope_service import apply_location_scope, can_access_location
from app.domain.enums import (
    ApprovalActorType,
    ApprovalDecision,
    Permission,
    RejectionReason,
    VisitSource,
    VisitStatus,
    role_has_permission,
)
from app.domain.models import Visit, VisitApproval, Visitor, VisitorType
from app.domain.visit_state import validate_transition


MAX_COMMENT_LENGTH = 500

APPROVAL_SOURCES = frozenset({
    VisitSource.SELF_REGISTRATION.value,
    VisitSource.ADVANCE_REGISTRATION.value,
})


class ApprovalError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class ApprovalConflictError(ApprovalError):
    def __init__(self, message: str = "This registration has already been processed."):
        super().__init__("APPROVAL_ALREADY_DECIDED", message, 409)


def _load_visit(db: Session, visit_id: int) -> Optional[Visit]:
    return (
        db.query(Visit)
        .options(
            joinedload(Visit.visitor).joinedload(Visitor.visitor_type),
            joinedload(Visit.location),
            joinedload(Visit.approvals),
        )
        .filter(Visit.id == visit_id)
        .first()
    )


def _require_read(ctx: AuthContext) -> None:
    if not role_has_permission(ctx.role, Permission.APPROVAL_READ):
        raise ApprovalError("forbidden", "Permission denied.", 403)


def _require_approve(ctx: AuthContext) -> None:
    if not role_has_permission(ctx.role, Permission.APPROVAL_APPROVE):
        raise ApprovalError("forbidden", "Permission denied.", 403)


def _require_reject(ctx: AuthContext) -> None:
    if not role_has_permission(ctx.role, Permission.APPROVAL_REJECT):
        raise ApprovalError("forbidden", "Permission denied.", 403)


def _require_site_access(ctx: AuthContext, location_id: int) -> None:
    if not can_access_location(ctx, location_id):
        raise ApprovalError("forbidden", "You do not have access to this site.", 403)


def _normalize_comment(comment: Optional[str]) -> Optional[str]:
    if comment is None:
        return None
    trimmed = comment.strip()
    if not trimmed:
        return None
    if len(trimmed) > MAX_COMMENT_LENGTH:
        raise ApprovalError("invalid_comment", f"Comment must be at most {MAX_COMMENT_LENGTH} characters.")
    return trimmed


def _build_visit_dict(visit: Visit) -> Dict[str, Any]:
    visitor = visit.visitor
    location = visit.location
    visitor_type_name = None
    if visitor and visitor.visitor_type:
        visitor_type_name = visitor.visitor_type.name

    history = [
        {
            "id": a.id,
            "decision": a.decision,
            "actor_type": a.actor_type,
            "actor_email": a.actor_email,
            "actor_role": a.actor_role,
            "actor_name": a.actor_name,
            "comment": a.comment,
            "reason_code": a.reason_code,
            "previous_status": a.previous_status,
            "new_status": a.new_status,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in sorted(visit.approvals, key=lambda x: x.created_at or datetime.min.replace(tzinfo=timezone.utc))
    ]

    return {
        "id": visit.id,
        "registration_reference": visit.registration_reference,
        "status": visit.status,
        "visitor_name": visitor.full_name if visitor else "",
        "visitor_mobile": visitor.phone if visitor else None,
        "visitor_email": visitor.email if visitor else None,
        "company": visitor.company if visitor else None,
        "visitor_type": visitor_type_name,
        "host_name": visit.host_name,
        "site_name": location.name if location else "",
        "site_id": visit.location_id,
        "purpose": visit.purpose,
        "expected_duration_minutes": visit.expected_duration_minutes,
        "policy_accepted": visit.policy_accepted,
        "policy_version": visit.policy_version,
        "submitted_at": visit.created_at.isoformat() if visit.created_at else None,
        "approval_history": history,
    }


def list_approvals(
    db: Session,
    ctx: AuthContext,
    status: Optional[str] = None,
    search: Optional[str] = None,
    site: Optional[int] = None,
    visitor_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[List[Dict[str, Any]], int, int]:
    _require_read(ctx)

    query = (
        db.query(Visit)
        .options(
            joinedload(Visit.visitor).joinedload(Visitor.visitor_type),
            joinedload(Visit.location),
        )
        .filter(Visit.source.in_(list(APPROVAL_SOURCES)))
    )

    query = apply_location_scope(query, ctx, db, site)

    if status and status.upper() != "ALL":
        query = query.filter(Visit.status == status.upper())
    else:
        query = query.filter(
            Visit.status.in_([
                VisitStatus.PENDING_APPROVAL.value,
                VisitStatus.APPROVED.value,
                VisitStatus.REJECTED.value,
            ])
        )

    if visitor_type:
        query = query.join(Visitor).join(VisitorType).filter(VisitorType.code == visitor_type.upper())

    if search and search.strip():
        term = f"%{search.strip()}%"
        if not visitor_type:
            query = query.join(Visitor, Visit.visitor_id == Visitor.id)
        query = query.filter(
            or_(
                Visitor.full_name.ilike(term),
                Visitor.company.ilike(term),
                Visit.registration_reference.ilike(term),
                Visit.host_name.ilike(term),
            )
        )

    pending_query = (
        db.query(Visit)
        .filter(
            Visit.source.in_(list(APPROVAL_SOURCES)),
            Visit.status == VisitStatus.PENDING_APPROVAL.value,
        )
    )
    pending_query = apply_location_scope(pending_query, ctx, db, site)
    pending_count = pending_query.count()

    total = query.count()
    visits = query.order_by(Visit.created_at.desc()).offset(offset).limit(limit).all()

    return [_build_visit_dict(v) for v in visits], total, pending_count


def get_approval_detail(db: Session, ctx: AuthContext, visit_id: int) -> Dict[str, Any]:
    _require_read(ctx)
    visit = _load_visit(db, visit_id)
    if not visit or visit.source not in APPROVAL_SOURCES:
        raise ApprovalError("not_found", "Registration not found.", 404)
    _require_site_access(ctx, visit.location_id)
    from app.application.compliance_service import evaluate_visit_compliance, compliance_summary_for_visit

    evaluate_visit_compliance(db, visit_id, trigger="approval_detail")
    db.flush()
    data = _build_visit_dict(visit)
    summary = compliance_summary_for_visit(db, visit_id)
    data["compliance_status"] = visit.compliance_status
    data["compliance_reason_summary"] = summary.get("reason_summary")
    data["compliance_signals"] = summary.get("signals", [])
    return data


def _atomic_status_update(
    db: Session,
    visit_id: int,
    expected_status: str,
    new_status: str,
) -> bool:
    result = db.execute(
        update(Visit)
        .where(Visit.id == visit_id, Visit.status == expected_status)
        .values(status=new_status)
    )
    return result.rowcount > 0


def approve_visit(
    db: Session,
    ctx: AuthContext,
    visit_id: int,
    comment: Optional[str] = None,
) -> Dict[str, Any]:
    _require_approve(ctx)
    visit = _load_visit(db, visit_id)
    if not visit or visit.source not in APPROVAL_SOURCES:
        raise ApprovalError("not_found", "Registration not found.", 404)
    _require_site_access(ctx, visit.location_id)
    return approve_visit_with_actor(db, visit_id, actor_from_auth(ctx), comment)


def approve_visit_with_actor(
    db: Session,
    visit_id: int,
    actor: ApprovalActor,
    comment: Optional[str] = None,
) -> Dict[str, Any]:
    comment = _normalize_comment(comment)

    visit = _load_visit(db, visit_id)
    if not visit or visit.source not in APPROVAL_SOURCES:
        raise ApprovalError("not_found", "Registration not found.", 404)

    from app.application.security_screening_service import ensure_allows_approval, SecurityScreeningError
    try:
        ensure_allows_approval(db, visit_id)
    except SecurityScreeningError as exc:
        raise ApprovalError(exc.code, exc.message, exc.status_code)

    from app.application.compliance_service import ensure_allows_approval as ensure_compliance_approval, ComplianceError
    try:
        ensure_compliance_approval(db, visit_id)
    except ComplianceError as exc:
        raise ApprovalError(exc.code, exc.message, exc.status_code)

    current = visit.status
    if current == VisitStatus.APPROVED.value:
        return _build_visit_dict(visit)
    if current != VisitStatus.PENDING_APPROVAL.value:
        raise ApprovalConflictError()

    validate_transition(VisitStatus(current), VisitStatus.APPROVED)

    if not _atomic_status_update(db, visit_id, VisitStatus.PENDING_APPROVAL.value, VisitStatus.APPROVED.value):
        db.refresh(visit)
        if visit.status == VisitStatus.APPROVED.value:
            return _build_visit_dict(_load_visit(db, visit_id) or visit)
        raise ApprovalConflictError()

    approval = VisitApproval(
        visit_id=visit_id,
        decision=ApprovalDecision.APPROVED.value,
        actor_type=actor.actor_type,
        actor_user_id=actor.actor_user_id,
        actor_host_id=actor.actor_host_id,
        actor_email=actor.actor_email,
        actor_role=actor.actor_role,
        actor_name=actor.actor_name,
        site_id=visit.location_id,
        comment=comment,
        previous_status=current,
        new_status=VisitStatus.APPROVED.value,
    )
    db.add(approval)

    audit = AuditService(db)
    audit.record(
        action="VISITOR_APPROVED",
        entity_type="visit",
        entity_id=str(visit_id),
        actor_id=actor.actor_user_id,
        actor_email=actor.actor_email,
        location_id=visit.location_id,
        before_value={"status": current, "actor_type": actor.actor_type},
        after_value={"status": VisitStatus.APPROVED.value, "comment": comment},
    )

    from app.application.invitation_service import activate_invitation
    activate_invitation(db, visit_id)

    from app.application.host_approval_service import revoke_pending_requests
    revoke_pending_requests(db, visit_id)

    db.commit()
    return _build_visit_dict(_load_visit(db, visit_id) or visit)


def reject_visit(
    db: Session,
    ctx: AuthContext,
    visit_id: int,
    reason_code: str,
    comment: Optional[str] = None,
) -> Dict[str, Any]:
    _require_reject(ctx)
    visit = _load_visit(db, visit_id)
    if not visit or visit.source not in APPROVAL_SOURCES:
        raise ApprovalError("not_found", "Registration not found.", 404)
    _require_site_access(ctx, visit.location_id)
    return reject_visit_with_actor(db, visit_id, actor_from_auth(ctx), reason_code, comment)


def reject_visit_with_actor(
    db: Session,
    visit_id: int,
    actor: ApprovalActor,
    reason_code: str,
    comment: Optional[str] = None,
) -> Dict[str, Any]:
    comment = _normalize_comment(comment)

    try:
        reason = RejectionReason(reason_code)
    except ValueError:
        raise ApprovalError("invalid_reason", "Invalid rejection reason.")

    if reason == RejectionReason.OTHER and not comment:
        raise ApprovalError("comment_required", "A comment is required when reason is Other.")

    visit = _load_visit(db, visit_id)
    if not visit or visit.source not in APPROVAL_SOURCES:
        raise ApprovalError("not_found", "Registration not found.", 404)

    current = visit.status
    if current == VisitStatus.REJECTED.value:
        return _build_visit_dict(visit)
    if current != VisitStatus.PENDING_APPROVAL.value:
        raise ApprovalConflictError()

    validate_transition(VisitStatus(current), VisitStatus.REJECTED)

    if not _atomic_status_update(db, visit_id, VisitStatus.PENDING_APPROVAL.value, VisitStatus.REJECTED.value):
        db.refresh(visit)
        if visit.status == VisitStatus.REJECTED.value:
            return _build_visit_dict(_load_visit(db, visit_id) or visit)
        raise ApprovalConflictError()

    approval = VisitApproval(
        visit_id=visit_id,
        decision=ApprovalDecision.REJECTED.value,
        actor_type=actor.actor_type,
        actor_user_id=actor.actor_user_id,
        actor_host_id=actor.actor_host_id,
        actor_email=actor.actor_email,
        actor_role=actor.actor_role,
        actor_name=actor.actor_name,
        site_id=visit.location_id,
        comment=comment,
        reason_code=reason.value,
        previous_status=current,
        new_status=VisitStatus.REJECTED.value,
    )
    db.add(approval)

    audit = AuditService(db)
    audit.record(
        action="VISITOR_REJECTED",
        entity_type="visit",
        entity_id=str(visit_id),
        actor_id=actor.actor_user_id,
        actor_email=actor.actor_email,
        location_id=visit.location_id,
        before_value={"status": current, "actor_type": actor.actor_type},
        after_value={"status": VisitStatus.REJECTED.value, "reason": reason.value, "comment": comment},
    )

    from app.application.host_approval_service import revoke_pending_requests
    revoke_pending_requests(db, visit_id)

    db.commit()
    return _build_visit_dict(_load_visit(db, visit_id) or visit)
