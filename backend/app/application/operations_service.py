"""Visitor arrival, check-in, checkout, and onsite operations."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import or_, and_, update
from sqlalchemy.orm import Session, joinedload

from app.application.audit_service import AuditService
from app.application.auth_service import AuthContext
from app.application.site_scope_service import apply_location_scope, can_access_location
from app.application.timezone_service import get_location_day_bounds
from app.domain.enums import CheckInMethod, Permission, VisitSource, VisitStatus, role_has_permission
from app.domain.models import Host, Location, Visit, Visitor, VisitorType
from app.domain.visit_state import validate_transition

MAX_COMMENT_LENGTH = 500

EXPECTED_TODAY_STATUSES = frozenset({
    VisitStatus.APPROVED.value,
    VisitStatus.ARRIVED.value,
    VisitStatus.CHECKED_IN.value,
    VisitStatus.ONSITE.value,
    VisitStatus.CHECKED_OUT.value,
})

ONSITE_STATUSES = frozenset({
    VisitStatus.ONSITE.value,
    VisitStatus.CHECKED_IN.value,
})


class OperationsError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class StateConflictError(OperationsError):
    def __init__(self, code: str, message: str):
        super().__init__(code, message, 409)


def _queue_host_arrival_notification(db: Session, visit: Visit, checked_in_at: datetime) -> None:
    if not visit.host_id:
        return
    host = db.query(Host).filter(Host.id == visit.host_id).first()
    if not host or not host.email:
        return
    visitor = visit.visitor
    location = visit.location
    checked_in_display = checked_in_at.strftime("%I:%M %p")
    payload = {
        "visitor_name": visitor.full_name if visitor else "",
        "company": visitor.company if visitor else None,
        "site_name": location.name if location else "",
        "purpose": visit.purpose,
        "checked_in_display": checked_in_display,
    }
    from app.application.notification_service import queue_visitor_arrived_email

    queue_visitor_arrived_email(
        db,
        visit_id=visit.id,
        host_id=visit.host_id,
        host_email=host.email,
        location_id=visit.location_id,
        payload=payload,
    )


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


def _require_permission(ctx: AuthContext, permission: Permission) -> None:
    if not role_has_permission(ctx.role, permission):
        raise OperationsError("forbidden", "Permission denied.", 403)


def _require_site_access(ctx: AuthContext, location_id: int) -> None:
    if not can_access_location(ctx, location_id):
        raise OperationsError("LOCATION_ACCESS_DENIED", "You do not have access to this site.", 403)


def _atomic_status_update(
    db: Session,
    visit_id: int,
    expected_status: str,
    new_status: str,
    extra_values: Optional[Dict[str, Any]] = None,
) -> bool:
    values: Dict[str, Any] = {"status": new_status}
    if extra_values:
        values.update(extra_values)
    result = db.execute(
        update(Visit)
        .where(Visit.id == visit_id, Visit.status == expected_status)
        .values(**values)
    )
    return result.rowcount > 0


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
            "actor_email": a.actor_email,
            "actor_role": a.actor_role,
            "comment": a.comment,
            "reason_code": a.reason_code,
            "previous_status": a.previous_status,
            "new_status": a.new_status,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in sorted(visit.approvals, key=lambda x: x.created_at or datetime.min.replace(tzinfo=timezone.utc))
    ]

    now = datetime.now(timezone.utc)
    overstay = False
    if visit.status == VisitStatus.ONSITE.value and visit.checked_in_at and visit.expected_duration_minutes:
        checked_in = visit.checked_in_at
        if checked_in.tzinfo is None:
            checked_in = checked_in.replace(tzinfo=timezone.utc)
        expected_end = checked_in + timedelta(minutes=visit.expected_duration_minutes)
        overstay = now > expected_end

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
        "site_city": location.city if location else None,
        "purpose": visit.purpose,
        "expected_duration_minutes": visit.expected_duration_minutes,
        "policy_accepted": visit.policy_accepted,
        "policy_version": visit.policy_version,
        "submitted_at": visit.created_at.isoformat() if visit.created_at else None,
        "scheduled_start": visit.scheduled_start.isoformat() if visit.scheduled_start else None,
        "scheduled_end": visit.scheduled_end.isoformat() if visit.scheduled_end else None,
        "arrived_at": visit.arrived_at.isoformat() if visit.arrived_at else None,
        "checked_in_at": visit.checked_in_at.isoformat() if visit.checked_in_at else None,
        "checked_out_at": visit.checked_out_at.isoformat() if visit.checked_out_at else None,
        "check_in_method": visit.check_in_method,
        "overstay": overstay,
        "approval_history": history,
        "is_walk_in": visit.source == VisitSource.SELF_REGISTRATION.value,
        "is_scheduled": visit.source == VisitSource.ADVANCE_REGISTRATION.value,
    }


def _apply_search(query, search: Optional[str]):
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.join(Visitor, Visit.visitor_id == Visitor.id)
        query = query.filter(
            or_(
                Visitor.full_name.ilike(term),
                Visitor.company.ilike(term),
                Visit.registration_reference.ilike(term),
                Visit.host_name.ilike(term),
            )
        )
    return query


def _filter_by_today(query, db: Session, site_filter: Optional[int], ctx: AuthContext):
    """Restrict to visits created today in the location timezone."""
    if site_filter is not None:
        loc = db.query(Location).filter(Location.id == site_filter).first()
        tz = loc.timezone if loc else None
        start, end = get_location_day_bounds(tz)
        return query.filter(Visit.created_at >= start, Visit.created_at < end)

    # Multiple locations: filter per-location today is complex; use UTC day as fallback
    # when no site selected — global admins typically pick a site on operational pages.
    start, end = get_location_day_bounds(None)
    return query.filter(Visit.created_at >= start, Visit.created_at < end)


def list_expected_today(
    db: Session,
    ctx: AuthContext,
    status: Optional[str] = None,
    search: Optional[str] = None,
    site: Optional[int] = None,
    visitor_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[List[Dict[str, Any]], int]:
    _require_permission(ctx, Permission.ARRIVAL_READ)

    query = (
        db.query(Visit)
        .options(
            joinedload(Visit.visitor).joinedload(Visitor.visitor_type),
            joinedload(Visit.location),
            joinedload(Visit.approvals),
        )
        .filter(Visit.source.in_([
            VisitSource.SELF_REGISTRATION.value,
            VisitSource.ADVANCE_REGISTRATION.value,
        ]))
    )
    query = apply_location_scope(query, ctx, db, site)

    if site is not None:
        loc = db.query(Location).filter(Location.id == site).first()
        if loc:
            start, end = get_location_day_bounds(loc.timezone)
            query = query.filter(
                or_(
                    and_(
                        Visit.source == VisitSource.SELF_REGISTRATION.value,
                        Visit.created_at >= start,
                        Visit.created_at < end,
                    ),
                    and_(
                        Visit.scheduled_start.isnot(None),
                        Visit.scheduled_start >= start,
                        Visit.scheduled_start < end,
                    ),
                )
            )
    else:
        start, end = get_location_day_bounds(None)
        query = query.filter(
            or_(
                and_(
                    Visit.source == VisitSource.SELF_REGISTRATION.value,
                    Visit.created_at >= start,
                    Visit.created_at < end,
                ),
                and_(
                    Visit.scheduled_start.isnot(None),
                    Visit.scheduled_start >= start,
                    Visit.scheduled_start < end,
                ),
            )
        )

    if status and status.upper() != "ALL":
        query = query.filter(Visit.status == status.upper())
    else:
        query = query.filter(Visit.status.in_(list(EXPECTED_TODAY_STATUSES)))

    if visitor_type:
        query = query.join(Visitor).join(VisitorType).filter(VisitorType.code == visitor_type.upper())

    query = _apply_search(query, search)

    total = query.count()
    visits = query.order_by(Visit.created_at.desc()).offset(offset).limit(limit).all()
    return [_build_visit_dict(v) for v in visits], total


def list_onsite(
    db: Session,
    ctx: AuthContext,
    search: Optional[str] = None,
    site: Optional[int] = None,
    visitor_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[List[Dict[str, Any]], int, int]:
    _require_permission(ctx, Permission.ONSITE_READ)

    query = (
        db.query(Visit)
        .options(
            joinedload(Visit.visitor).joinedload(Visitor.visitor_type),
            joinedload(Visit.location),
            joinedload(Visit.approvals),
        )
        .filter(Visit.status == VisitStatus.ONSITE.value)
    )
    query = apply_location_scope(query, ctx, db, site)

    if visitor_type:
        query = query.join(Visitor).join(VisitorType).filter(VisitorType.code == visitor_type.upper())

    query = _apply_search(query, search)

    count_query = (
        db.query(Visit)
        .filter(Visit.status == VisitStatus.ONSITE.value)
    )
    count_query = apply_location_scope(count_query, ctx, db, site)
    onsite_count = count_query.count()

    total = query.count()
    visits = query.order_by(Visit.checked_in_at.desc()).offset(offset).limit(limit).all()
    return [_build_visit_dict(v) for v in visits], total, onsite_count


def list_visitor_visits(
    db: Session,
    ctx: AuthContext,
    status: Optional[str] = None,
    search: Optional[str] = None,
    site: Optional[int] = None,
    visitor_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[List[Dict[str, Any]], int]:
    """Operational visitor visit list for staff with visitor.read (location-scoped)."""
    _require_permission(ctx, Permission.VISITOR_READ)

    cutoff = datetime.now(timezone.utc) - timedelta(days=120)
    query = (
        db.query(Visit)
        .options(
            joinedload(Visit.visitor).joinedload(Visitor.visitor_type),
            joinedload(Visit.location),
            joinedload(Visit.approvals),
        )
        .filter(Visit.status != VisitStatus.DRAFT.value)
        .filter(Visit.updated_at >= cutoff)
    )
    query = apply_location_scope(query, ctx, db, site)

    if status and status.upper() != "ALL":
        query = query.filter(Visit.status == status.upper())

    if visitor_type:
        query = query.join(Visitor).join(VisitorType).filter(VisitorType.code == visitor_type.upper())

    query = _apply_search(query, search)

    total = query.count()
    visits = query.order_by(Visit.updated_at.desc()).offset(offset).limit(limit).all()
    return [_build_visit_dict(v) for v in visits], total


def get_visit_detail(db: Session, ctx: AuthContext, visit_id: int) -> Dict[str, Any]:
    _require_permission(ctx, Permission.VISITOR_READ)
    visit = _load_visit(db, visit_id)
    if not visit:
        raise OperationsError("VISIT_NOT_FOUND", "Visit not found.", 404)
    _require_site_access(ctx, visit.location_id)
    return _build_visit_dict(visit)


def mark_arrived(db: Session, ctx: AuthContext, visit_id: int) -> Dict[str, Any]:
    _require_permission(ctx, Permission.ARRIVAL_MANAGE)

    visit = _load_visit(db, visit_id)
    if not visit:
        raise OperationsError("VISIT_NOT_FOUND", "Visit not found.", 404)
    _require_site_access(ctx, visit.location_id)

    current = visit.status
    if current == VisitStatus.ARRIVED.value:
        return _build_visit_dict(visit)
    if current != VisitStatus.APPROVED.value:
        raise StateConflictError("INVALID_VISIT_STATE", "Only approved visitors can be marked as arrived.")

    validate_transition(VisitStatus(current), VisitStatus.ARRIVED)
    now = datetime.now(timezone.utc)

    if not _atomic_status_update(
        db,
        visit_id,
        VisitStatus.APPROVED.value,
        VisitStatus.ARRIVED.value,
        {
            "arrived_at": now,
            "arrival_recorded_by_user_id": ctx.user_id,
            "arrival_location_id": visit.location_id,
        },
    ):
        db.refresh(visit)
        if visit.status == VisitStatus.ARRIVED.value:
            return _build_visit_dict(_load_visit(db, visit_id) or visit)
        raise StateConflictError("INVALID_VISIT_STATE", "Visit state changed. Refresh and try again.")

    audit = AuditService(db)
    audit.record(
        action="VISITOR_ARRIVED",
        entity_type="visit",
        entity_id=str(visit_id),
        actor_id=ctx.user_id,
        actor_email=ctx.email,
        location_id=visit.location_id,
        before_value={"status": current, "actor_role": ctx.role.value},
        after_value={"status": VisitStatus.ARRIVED.value},
    )

    db.commit()
    return _build_visit_dict(_load_visit(db, visit_id) or visit)


def check_in_visit(db: Session, ctx: AuthContext, visit_id: int) -> Dict[str, Any]:
    _require_permission(ctx, Permission.CHECKIN_PERFORM)

    from app.application.security_screening_service import ensure_allows_checkin, SecurityScreeningError
    try:
        ensure_allows_checkin(db, visit_id)
    except SecurityScreeningError as exc:
        raise OperationsError(exc.code, exc.message, exc.status_code)

    from app.application.compliance_service import ensure_allows_checkin, ComplianceError
    try:
        ensure_allows_checkin(db, visit_id)
    except ComplianceError as exc:
        raise OperationsError(exc.code, exc.message, exc.status_code)

    from app.application.emergency_roll_call_service import ensure_allows_checkin as ensure_emergency_allows_checkin, EmergencyRollCallError
    try:
        ensure_emergency_allows_checkin(db, visit_id)
    except EmergencyRollCallError as exc:
        raise OperationsError(exc.code, exc.message, exc.status_code)

    visit = _load_visit(db, visit_id)
    if not visit:
        raise OperationsError("VISIT_NOT_FOUND", "Visit not found.", 404)
    _require_site_access(ctx, visit.location_id)

    current = visit.status
    if current == VisitStatus.ONSITE.value:
        return _build_visit_dict(visit)
    if current != VisitStatus.ARRIVED.value:
        if current in (VisitStatus.CHECKED_IN.value, VisitStatus.ONSITE.value):
            raise StateConflictError("ALREADY_CHECKED_IN", "This visitor is already checked in.")
        raise StateConflictError("INVALID_VISIT_STATE", "Visitor must be marked arrived before check-in.")

    validate_transition(VisitStatus(current), VisitStatus.ONSITE)
    now = datetime.now(timezone.utc)

    if not _atomic_status_update(
        db,
        visit_id,
        VisitStatus.ARRIVED.value,
        VisitStatus.ONSITE.value,
        {
            "checked_in_at": now,
            "checked_in_by_user_id": ctx.user_id,
            "check_in_location_id": visit.location_id,
            "check_in_method": CheckInMethod.ADMIN_MANUAL.value,
        },
    ):
        db.refresh(visit)
        if visit.status == VisitStatus.ONSITE.value:
            return _build_visit_dict(_load_visit(db, visit_id) or visit)
        raise StateConflictError("INVALID_VISIT_STATE", "Visit state changed. Refresh and try again.")

    audit = AuditService(db)
    audit.record(
        action="VISITOR_CHECKED_IN",
        entity_type="visit",
        entity_id=str(visit_id),
        actor_id=ctx.user_id,
        actor_email=ctx.email,
        location_id=visit.location_id,
        before_value={"status": current, "actor_role": ctx.role.value},
        after_value={"status": VisitStatus.ONSITE.value, "method": CheckInMethod.ADMIN_MANUAL.value},
    )

    _queue_host_arrival_notification(db, visit, now)

    from app.application.access_provisioning_service import request_access_on_checkin
    request_access_on_checkin(db, visit_id, actor_id=ctx.user_id, actor_email=ctx.email)

    db.commit()
    from app.application.access_provisioning_service import process_pending_access_attempts
    process_pending_access_attempts(db)
    db.commit()
    from app.application.notification_dispatch_service import dispatch_pending_notifications
    dispatch_pending_notifications(db)
    return _build_visit_dict(_load_visit(db, visit_id) or visit)


def check_out_visit(db: Session, ctx: AuthContext, visit_id: int) -> Dict[str, Any]:
    _require_permission(ctx, Permission.CHECKOUT_PERFORM)

    visit = _load_visit(db, visit_id)
    if not visit:
        raise OperationsError("VISIT_NOT_FOUND", "Visit not found.", 404)
    _require_site_access(ctx, visit.location_id)

    current = visit.status
    if current == VisitStatus.CHECKED_OUT.value:
        return _build_visit_dict(visit)
    if current != VisitStatus.ONSITE.value:
        raise StateConflictError("INVALID_VISIT_STATE", "Only onsite visitors can be checked out.")

    validate_transition(VisitStatus(current), VisitStatus.CHECKED_OUT)
    now = datetime.now(timezone.utc)

    if not _atomic_status_update(
        db,
        visit_id,
        VisitStatus.ONSITE.value,
        VisitStatus.CHECKED_OUT.value,
        {"checked_out_at": now},
    ):
        db.refresh(visit)
        if visit.status == VisitStatus.CHECKED_OUT.value:
            return _build_visit_dict(_load_visit(db, visit_id) or visit)
        raise StateConflictError("VISITOR_ALREADY_CHECKED_OUT", "This visitor has already been checked out.")

    audit = AuditService(db)
    audit.record(
        action="VISITOR_CHECKED_OUT",
        entity_type="visit",
        entity_id=str(visit_id),
        actor_id=ctx.user_id,
        actor_email=ctx.email,
        location_id=visit.location_id,
        before_value={"status": current, "actor_role": ctx.role.value},
        after_value={"status": VisitStatus.CHECKED_OUT.value},
    )

    from app.application.badge_service import expire_badges_for_visit
    expire_badges_for_visit(db, visit_id, actor_id=ctx.user_id, actor_email=ctx.email)

    from app.application.emergency_roll_call_service import mark_visit_checked_out_after_emergency
    mark_visit_checked_out_after_emergency(db, visit_id)

    from app.application.access_provisioning_service import request_access_revoke_on_checkout
    request_access_revoke_on_checkout(db, visit_id, actor_id=ctx.user_id, actor_email=ctx.email)

    db.commit()
    from app.application.access_provisioning_service import process_pending_access_attempts
    process_pending_access_attempts(db)
    db.commit()
    return _build_visit_dict(_load_visit(db, visit_id) or visit)
