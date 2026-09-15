"""Host approval request lifecycle and secure link handling."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import update
from sqlalchemy.orm import Session, joinedload

from app.application.audit_service import AuditService
from app.application.approval_actor import actor_from_host
from app.application.approval_service import (
    ApprovalConflictError,
    ApprovalError,
    approve_visit_with_actor,
    reject_visit_with_actor,
)
from app.application.notification_dispatch_service import dispatch_pending_notifications
from app.application.notification_service import queue_host_approval_request_email
from app.application.token_service import generate_host_approval_token, hash_host_approval_token
from app.core.config import settings
from app.domain.enums import (
    ApprovalDecision,
    HostApprovalRequestStatus,
    VisitSource,
    VisitStatus,
)
from app.domain.models import Host, HostApprovalRequest, Location, Visit, Visitor


class HostApprovalError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def compute_host_approval_expiry(visit: Visit, now: Optional[datetime] = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    ttl_expiry = now + timedelta(hours=settings.host_approval_token_ttl_hours)
    if visit.scheduled_end:
        scheduled_end = visit.scheduled_end
        if scheduled_end.tzinfo is None:
            scheduled_end = scheduled_end.replace(tzinfo=timezone.utc)
        grace = timedelta(minutes=settings.invitation_late_grace_minutes)
        visit_expiry = scheduled_end + grace
        return min(ttl_expiry, visit_expiry)
    return ttl_expiry


def _load_visit(db: Session, visit_id: int) -> Optional[Visit]:
    return (
        db.query(Visit)
        .options(
            joinedload(Visit.visitor).joinedload(Visitor.visitor_type),
            joinedload(Visit.location),
            joinedload(Visit.host),
        )
        .filter(Visit.id == visit_id)
        .first()
    )


def _build_email_payload(visit: Visit) -> Dict[str, Any]:
    visitor = visit.visitor
    location = visit.location
    is_walk_in = visit.source == VisitSource.SELF_REGISTRATION.value
    scheduled_display = None
    if visit.scheduled_start:
        scheduled_display = visit.scheduled_start.strftime("%d %b %Y · %I:%M %p")
    return {
        "visitor_name": visitor.full_name if visitor else "",
        "company": visitor.company if visitor else None,
        "site_name": location.name if location else "",
        "purpose": visit.purpose,
        "location_id": visit.location_id,
        "is_walk_in": is_walk_in,
        "scheduled_display": scheduled_display,
        "expected_duration_minutes": visit.expected_duration_minutes,
    }


def _approval_link(token: str) -> str:
    return f"{settings.public_app_origin}/host/approval/{token}"


def revoke_pending_requests(db: Session, visit_id: int, reason: str = "resolved") -> None:
    now = datetime.now(timezone.utc)
    pending = (
        db.query(HostApprovalRequest)
        .filter(
            HostApprovalRequest.visit_id == visit_id,
            HostApprovalRequest.status == HostApprovalRequestStatus.PENDING.value,
        )
        .all()
    )
    for req in pending:
        req.status = HostApprovalRequestStatus.REVOKED.value
        req.revoked_at = now


def create_host_approval_request(
    db: Session,
    visit_id: int,
    created_for_reason: str = "INITIAL",
    resend: bool = False,
) -> Optional[HostApprovalRequest]:
    visit = _load_visit(db, visit_id)
    if not visit or visit.status != VisitStatus.PENDING_APPROVAL.value:
        return None
    if not visit.host_id:
        return None

    host = visit.host or db.query(Host).filter(Host.id == visit.host_id).first()
    if not host or not host.is_active:
        return None
    host_email = (host.email or "").strip()
    if not host_email:
        return None

    if resend:
        revoke_pending_requests(db, visit_id, reason="resend")

    existing_pending = (
        db.query(HostApprovalRequest)
        .filter(
            HostApprovalRequest.visit_id == visit_id,
            HostApprovalRequest.host_id == visit.host_id,
            HostApprovalRequest.status == HostApprovalRequestStatus.PENDING.value,
        )
        .first()
    )
    if existing_pending and not resend:
        return existing_pending

    raw_token = generate_host_approval_token()
    token_hash = hash_host_approval_token(raw_token)
    now = datetime.now(timezone.utc)
    expires_at = compute_host_approval_expiry(visit, now)

    request = HostApprovalRequest(
        visit_id=visit_id,
        host_id=visit.host_id,
        host_email_snapshot=host_email,
        token_hash=token_hash,
        status=HostApprovalRequestStatus.PENDING.value,
        expires_at=expires_at,
        created_for_reason=created_for_reason,
    )
    db.add(request)
    db.flush()

    payload = _build_email_payload(visit)
    approval_url = _approval_link(raw_token)
    dev_url = None
    if settings.email_provider == "dev_outbox" and not settings.is_production:
        dev_url = approval_url
    else:
        from app.application.data_encryption_service import encrypt_value, EncryptionError
        try:
            payload["approval_url_enc"] = encrypt_value(approval_url)
        except EncryptionError:
            if settings.is_production:
                raise HostApprovalError("encryption_unavailable", "Secure delivery is not configured.", 503)
            dev_url = approval_url
    queue_host_approval_request_email(
        db,
        visit_id=visit_id,
        host_id=visit.host_id,
        host_email=host_email,
        request_id=request.id,
        payload=payload,
        dev_action_url=dev_url,
        is_resend=resend,
    )

    audit = AuditService(db)
    audit.record(
        action="HOST_APPROVAL_REQUEST_CREATED",
        entity_type="host_approval_request",
        entity_id=str(request.id),
        location_id=visit.location_id,
        after_value={"visit_id": visit_id, "host_id": visit.host_id, "reason": created_for_reason},
    )

    # Transient raw token for dev only — never persisted
    request._raw_token = raw_token  # type: ignore[attr-defined]
    return request


def maybe_create_for_pending_visit(db: Session, visit_id: int) -> None:
    create_host_approval_request(db, visit_id, created_for_reason="INITIAL")


def _load_request_by_token(db: Session, token: str) -> Optional[HostApprovalRequest]:
    if not token or len(token) < 16:
        return None
    token_hash = hash_host_approval_token(token.strip())
    return (
        db.query(HostApprovalRequest)
        .options(
            joinedload(HostApprovalRequest.visit).joinedload(Visit.visitor).joinedload(Visitor.visitor_type),
            joinedload(HostApprovalRequest.visit).joinedload(Visit.location),
            joinedload(HostApprovalRequest.host),
        )
        .filter(HostApprovalRequest.token_hash == token_hash)
        .first()
    )


def _visit_terminal_state(visit: Visit) -> Optional[str]:
    if visit.status == VisitStatus.CANCELLED.value:
        return "CANCELLED"
    if visit.status in (VisitStatus.ONSITE.value, VisitStatus.CHECKED_IN.value, VisitStatus.CHECKED_OUT.value):
        return "PROCESSED"
    if visit.status == VisitStatus.APPROVED.value:
        return "APPROVED"
    if visit.status == VisitStatus.REJECTED.value:
        return "REJECTED"
    return None


def get_public_host_approval_summary(db: Session, token: str) -> Dict[str, Any]:
    request = _load_request_by_token(db, token)
    if not request:
        raise HostApprovalError("INVALID_LINK", "This approval link is invalid.", 404)

    visit = request.visit
    if not visit:
        raise HostApprovalError("INVALID_LINK", "This approval link is invalid.", 404)

    if visit.host_id != request.host_id:
        raise HostApprovalError("INVALID_LINK", "This approval link is no longer valid.", 400)

    terminal = _visit_terminal_state(visit)
    now = datetime.now(timezone.utc)

    if request.status == HostApprovalRequestStatus.REVOKED.value:
        return _public_state("REVOKED", visit, request, "This visitor request has already been processed.")
    if request.status == HostApprovalRequestStatus.EXPIRED.value or _as_utc(request.expires_at) < now:
        if request.status == HostApprovalRequestStatus.PENDING.value:
            request.status = HostApprovalRequestStatus.EXPIRED.value
            db.commit()
        return _public_state("EXPIRED", visit, request, "This approval link has expired.")

    if request.status in (HostApprovalRequestStatus.APPROVED.value, HostApprovalRequestStatus.REJECTED.value):
        return _public_state("ALREADY_PROCESSED", visit, request, "This visitor request has already been processed.")

    if terminal == "CANCELLED":
        return _public_state("CANCELLED", visit, request, "This visit has been cancelled.")
    if terminal in ("APPROVED", "REJECTED", "PROCESSED"):
        return _public_state("ALREADY_PROCESSED", visit, request, "This visitor request has already been processed.")

    if visit.status != VisitStatus.PENDING_APPROVAL.value:
        return _public_state("ALREADY_PROCESSED", visit, request, "This visitor request has already been processed.")

    return _public_state("PENDING", visit, request)


def _public_state(code: str, visit: Visit, request: HostApprovalRequest, message: Optional[str] = None) -> Dict[str, Any]:
    visitor = visit.visitor
    location = visit.location
    visitor_type_name = visitor.visitor_type.name if visitor and visitor.visitor_type else None
    is_walk_in = visit.source == VisitSource.SELF_REGISTRATION.value
    scheduled_display = None
    if visit.scheduled_start:
        scheduled_display = visit.scheduled_start.strftime("%d %b %Y · %I:%M %p")

    return {
        "state": code,
        "message": message,
        "visit_status": visit.status,
        "visitor_name": visitor.full_name if visitor else "",
        "company": visitor.company if visitor else None,
        "visitor_type": visitor_type_name,
        "site_name": location.name if location else "",
        "purpose": visit.purpose,
        "is_walk_in": is_walk_in,
        "scheduled_display": scheduled_display,
        "expected_duration_minutes": visit.expected_duration_minutes,
        "can_approve": code == "PENDING",
        "can_reject": code == "PENDING",
    }


def _mark_request_responded(
    db: Session,
    request: HostApprovalRequest,
    response: str,
) -> bool:
    now = datetime.now(timezone.utc)
    result = db.execute(
        update(HostApprovalRequest)
        .where(
            HostApprovalRequest.id == request.id,
            HostApprovalRequest.status == HostApprovalRequestStatus.PENDING.value,
        )
        .values(
            status=response,
            response=response,
            responded_at=now,
        )
    )
    return result.rowcount > 0


def host_approve(db: Session, token: str) -> Dict[str, Any]:
    summary = get_public_host_approval_summary(db, token)
    if summary["state"] != "PENDING":
        return summary

    request = _load_request_by_token(db, token)
    if not request:
        raise HostApprovalError("INVALID_LINK", "This approval link is invalid.", 404)

    visit = request.visit
    host = request.host
    actor = actor_from_host(request.host_id, request.host_email_snapshot, host.name if host else visit.host_name or "Host")

    from app.application.security_screening_service import ensure_allows_approval, SecurityScreeningError
    try:
        ensure_allows_approval(db, visit.id)
    except SecurityScreeningError as exc:
        raise HostApprovalError(exc.code, exc.message, exc.status_code)

    from app.application.compliance_service import ensure_allows_approval as ensure_compliance_approval, ComplianceError
    try:
        ensure_compliance_approval(db, visit.id)
    except ComplianceError as exc:
        raise HostApprovalError(exc.code, exc.message, exc.status_code)

    try:
        approve_visit_with_actor(db, visit.id, actor, comment=None)
    except ApprovalConflictError:
        db.refresh(visit)
        return get_public_host_approval_summary(db, token)
    except ApprovalError as exc:
        raise HostApprovalError(exc.code, exc.message, exc.status_code)

    _mark_request_responded(db, request, HostApprovalRequestStatus.APPROVED.value)
    AuditService(db).record(
        action="HOST_APPROVAL_APPROVED",
        entity_type="host_approval_request",
        entity_id=str(request.id),
        location_id=visit.location_id,
        after_value={"visit_id": visit.id, "host_id": request.host_id},
    )
    db.commit()
    dispatch_pending_notifications(db)
    return {"state": "APPROVED", "message": "Visitor approved successfully.", "visitor_name": summary["visitor_name"]}


def host_reject(
    db: Session,
    token: str,
    reason_code: str,
    comment: Optional[str] = None,
) -> Dict[str, Any]:
    summary = get_public_host_approval_summary(db, token)
    if summary["state"] != "PENDING":
        return summary

    request = _load_request_by_token(db, token)
    if not request:
        raise HostApprovalError("INVALID_LINK", "This approval link is invalid.", 404)

    visit = request.visit
    host = request.host
    actor = actor_from_host(request.host_id, request.host_email_snapshot, host.name if host else visit.host_name or "Host")

    try:
        reject_visit_with_actor(db, visit.id, actor, reason_code=reason_code, comment=comment)
    except ApprovalConflictError:
        db.refresh(visit)
        return get_public_host_approval_summary(db, token)
    except ApprovalError as exc:
        raise HostApprovalError(exc.code, exc.message, exc.status_code)

    _mark_request_responded(db, request, HostApprovalRequestStatus.REJECTED.value)
    AuditService(db).record(
        action="HOST_APPROVAL_REJECTED",
        entity_type="host_approval_request",
        entity_id=str(request.id),
        location_id=visit.location_id,
        after_value={"visit_id": visit.id, "host_id": request.host_id, "reason": reason_code},
    )
    db.commit()
    dispatch_pending_notifications(db)
    return {"state": "REJECTED", "message": "Visitor request rejected.", "visitor_name": summary["visitor_name"]}


def resend_host_approval(db: Session, visit_id: int, actor_user_id: int, actor_email: str) -> Dict[str, Any]:
    visit = _load_visit(db, visit_id)
    if not visit:
        raise HostApprovalError("not_found", "Visit not found.", 404)
    if visit.status != VisitStatus.PENDING_APPROVAL.value:
        raise HostApprovalError("INVALID_VISIT_STATE", "Host approval can only be resent while pending approval.", 409)

    recent = (
        db.query(HostApprovalRequest)
        .filter(HostApprovalRequest.visit_id == visit_id)
        .order_by(HostApprovalRequest.created_at.desc())
        .first()
    )
    if recent and recent.created_at:
        cooldown = timedelta(minutes=settings.host_approval_resend_cooldown_minutes)
        created = recent.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - created < cooldown:
            raise HostApprovalError("RATE_LIMITED", "Please wait before resending host approval.", 429)

    request = create_host_approval_request(db, visit_id, created_for_reason="RESEND", resend=True)
    if not request:
        raise HostApprovalError("host_unavailable", "Unable to create host approval request.", 400)

    db.commit()
    dispatch_pending_notifications(db)
    return {"success": True, "request_id": request.id}
