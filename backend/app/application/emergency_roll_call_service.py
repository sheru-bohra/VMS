"""Emergency / evacuation visitor roll-call."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, or_, update
from sqlalchemy.orm import Session, joinedload

from app.application.audit_service import AuditService
from app.application.auth_service import AuthContext
from app.application.site_scope_service import can_access_location
from app.domain.enums import (
    BadgeStatus,
    EmergencyEventStatus,
    EmergencyReason,
    Permission,
    RollCallEntryStatus,
    VisitStatus,
    role_has_permission,
)
from app.domain.models import (
    AdminUser,
    EmergencyEvent,
    EmergencyRollCallAction,
    EmergencyRollCallEntry,
    Location,
    Visit,
    Visitor,
    VisitorBadge,
)


class EmergencyRollCallError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _require_read(ctx: AuthContext) -> None:
    if not role_has_permission(ctx.role, Permission.EMERGENCY_READ):
        raise EmergencyRollCallError("forbidden", "Permission denied.", 403)


def _require_start(ctx: AuthContext) -> None:
    if not role_has_permission(ctx.role, Permission.EMERGENCY_START):
        raise EmergencyRollCallError("forbidden", "Permission denied.", 403)


def _require_rollcall(ctx: AuthContext) -> None:
    if not role_has_permission(ctx.role, Permission.EMERGENCY_ROLLCALL):
        raise EmergencyRollCallError("forbidden", "Permission denied.", 403)


def _require_close(ctx: AuthContext) -> None:
    if not role_has_permission(ctx.role, Permission.EMERGENCY_CLOSE):
        raise EmergencyRollCallError("forbidden", "Permission denied.", 403)


def _require_history(ctx: AuthContext) -> None:
    if not role_has_permission(ctx.role, Permission.EMERGENCY_HISTORY_READ):
        raise EmergencyRollCallError("forbidden", "Permission denied.", 403)


def _require_site(ctx: AuthContext, location_id: int) -> None:
    if not can_access_location(ctx, location_id):
        raise EmergencyRollCallError("forbidden", "You do not have access to this location.", 403)


def _active_badge_number(visit: Visit) -> Optional[str]:
    for badge in visit.badges:
        if badge.status == BadgeStatus.ACTIVE.value:
            return badge.badge_number
    return None


def _count_entries_by_status(db: Session, emergency_id: int) -> Dict[str, int]:
    rows = (
        db.query(EmergencyRollCallEntry.status, func.count(EmergencyRollCallEntry.id))
        .filter(EmergencyRollCallEntry.emergency_event_id == emergency_id)
        .group_by(EmergencyRollCallEntry.status)
        .all()
    )
    counts = {s.value: 0 for s in RollCallEntryStatus}
    for status, count in rows:
        counts[status] = count
    total = sum(counts.values())
    return {
        "total": total,
        "unaccounted": counts.get(RollCallEntryStatus.UNACCOUNTED.value, 0),
        "safe": counts.get(RollCallEntryStatus.SAFE.value, 0),
        "not_located": counts.get(RollCallEntryStatus.NOT_LOCATED.value, 0),
        "left_premises": counts.get(RollCallEntryStatus.LEFT_PREMISES.value, 0),
        "pending": counts.get(RollCallEntryStatus.UNACCOUNTED.value, 0),
    }


def _build_event_dict(db: Session, event: EmergencyEvent, include_counts: bool = True) -> Dict[str, Any]:
    loc = event.location or db.query(Location).filter(Location.id == event.location_id).first()
    started_by = db.query(AdminUser).filter(AdminUser.id == event.started_by_user_id).first()
    closed_by = None
    if event.closed_by_user_id:
        closed_by = db.query(AdminUser).filter(AdminUser.id == event.closed_by_user_id).first()
    counts = _count_entries_by_status(db, event.id) if include_counts else {}
    return {
        "id": event.id,
        "location_id": event.location_id,
        "location_name": loc.name if loc else None,
        "location_code": loc.code if loc else None,
        "status": event.status,
        "started_at": event.started_at.isoformat() if event.started_at else None,
        "started_by_user_id": event.started_by_user_id,
        "started_by_name": started_by.display_name if started_by else None,
        "started_by_email": started_by.email if started_by else None,
        "reason": event.reason,
        "notes": event.notes,
        "visitor_snapshot_count": event.visitor_snapshot_count,
        "closed_at": event.closed_at.isoformat() if event.closed_at else None,
        "closed_by_user_id": event.closed_by_user_id,
        "closed_by_name": closed_by.display_name if closed_by else None,
        "closure_comment": event.closure_comment,
        "counts": counts,
    }


def _build_entry_dict(db: Session, entry: EmergencyRollCallEntry) -> Dict[str, Any]:
    updated_by = None
    if entry.status_updated_by_user_id:
        user = db.query(AdminUser).filter(AdminUser.id == entry.status_updated_by_user_id).first()
        updated_by = user.display_name or user.email if user else None
    visit_status = None
    if entry.visit:
        visit_status = entry.visit.status
    return {
        "id": entry.id,
        "emergency_event_id": entry.emergency_event_id,
        "visit_id": entry.visit_id,
        "visitor_id": entry.visitor_id,
        "visitor_name": entry.snapshot_visitor_name,
        "company": entry.snapshot_company,
        "visitor_type": entry.snapshot_visitor_type,
        "host_name": entry.snapshot_host_name,
        "mobile": entry.snapshot_mobile,
        "registration_reference": entry.snapshot_registration_reference,
        "badge_number": entry.snapshot_badge_number,
        "checked_in_at": entry.snapshot_checked_in_at.isoformat() if entry.snapshot_checked_in_at else None,
        "status": entry.status,
        "status_label": _status_label(entry.status),
        "status_updated_at": entry.status_updated_at.isoformat() if entry.status_updated_at else None,
        "status_updated_by_name": updated_by,
        "comment": entry.comment,
        "version": entry.version,
        "visit_checked_out_after_start": entry.visit_checked_out_after_start,
        "current_visit_status": visit_status,
    }


def _status_label(status: str) -> str:
    if status == RollCallEntryStatus.UNACCOUNTED.value:
        return "Pending"
    return status.replace("_", " ")


def get_active_emergency_for_location(db: Session, location_id: int) -> Optional[EmergencyEvent]:
    return (
        db.query(EmergencyEvent)
        .filter(
            EmergencyEvent.location_id == location_id,
            EmergencyEvent.status == EmergencyEventStatus.ACTIVE.value,
        )
        .first()
    )


def location_has_active_emergency(db: Session, location_id: int) -> bool:
    return get_active_emergency_for_location(db, location_id) is not None


def ensure_allows_checkin(db: Session, visit_id: int) -> None:
    visit = db.query(Visit).filter(Visit.id == visit_id).first()
    if not visit:
        return
    if location_has_active_emergency(db, visit.location_id):
        raise EmergencyRollCallError(
            "LOCATION_EMERGENCY_ACTIVE",
            "Visitor check-in is temporarily unavailable while an emergency roll-call is active.",
            403,
        )


def mark_visit_checked_out_after_emergency(db: Session, visit_id: int) -> None:
    visit = db.query(Visit).filter(Visit.id == visit_id).first()
    if not visit:
        return
    event = get_active_emergency_for_location(db, visit.location_id)
    if not event:
        return
    entry = (
        db.query(EmergencyRollCallEntry)
        .filter(
            EmergencyRollCallEntry.emergency_event_id == event.id,
            EmergencyRollCallEntry.visit_id == visit_id,
        )
        .first()
    )
    if entry:
        entry.visit_checked_out_after_start = True
        db.flush()


def count_onsite_visitors(db: Session, ctx: AuthContext, location_id: int) -> int:
    _require_read(ctx)
    _require_site(ctx, location_id)
    return (
        db.query(Visit)
        .filter(Visit.location_id == location_id, Visit.status == VisitStatus.ONSITE.value)
        .count()
    )


def list_active_emergencies(db: Session, ctx: AuthContext, location_id: Optional[int] = None) -> List[Dict[str, Any]]:
    _require_read(ctx)
    query = db.query(EmergencyEvent).filter(EmergencyEvent.status == EmergencyEventStatus.ACTIVE.value)
    if location_id is not None:
        _require_site(ctx, location_id)
        query = query.filter(EmergencyEvent.location_id == location_id)
    elif ctx.role.value not in ("GLOBAL_ADMIN", "HEAD_ADMIN"):
        if not ctx.location_ids:
            return []
        query = query.filter(EmergencyEvent.location_id.in_(ctx.location_ids))
    events = query.order_by(EmergencyEvent.started_at.desc()).all()
    return [_build_event_dict(db, e) for e in events]


def list_emergency_overview(db: Session, ctx: AuthContext) -> List[Dict[str, Any]]:
    _require_read(ctx)
    if ctx.role.value not in ("GLOBAL_ADMIN", "HEAD_ADMIN"):
        raise EmergencyRollCallError("forbidden", "Cross-location overview requires management access.", 403)
    locations = db.query(Location).filter(Location.is_active.is_(True)).order_by(Location.name).all()
    result = []
    for loc in locations:
        active = get_active_emergency_for_location(db, loc.id)
        onsite = db.query(Visit).filter(Visit.location_id == loc.id, Visit.status == VisitStatus.ONSITE.value).count()
        result.append({
            "location_id": loc.id,
            "location_name": loc.name,
            "location_code": loc.code,
            "has_active_emergency": active is not None,
            "active_emergency_id": active.id if active else None,
            "current_onsite_count": onsite,
        })
    return result


def list_emergency_history(
    db: Session,
    ctx: AuthContext,
    location_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[List[Dict[str, Any]], int]:
    _require_history(ctx)
    query = db.query(EmergencyEvent).filter(EmergencyEvent.status == EmergencyEventStatus.CLOSED.value)
    if location_id is not None:
        _require_site(ctx, location_id)
        query = query.filter(EmergencyEvent.location_id == location_id)
    elif ctx.role.value not in ("GLOBAL_ADMIN", "HEAD_ADMIN"):
        if not ctx.location_ids:
            return [], 0
        query = query.filter(EmergencyEvent.location_id.in_(ctx.location_ids))
    total = query.count()
    events = query.order_by(EmergencyEvent.closed_at.desc()).offset(offset).limit(limit).all()
    return [_build_event_dict(db, e) for e in events], total


def get_emergency(db: Session, ctx: AuthContext, emergency_id: int) -> Dict[str, Any]:
    _require_read(ctx)
    event = db.query(EmergencyEvent).filter(EmergencyEvent.id == emergency_id).first()
    if not event:
        raise EmergencyRollCallError("not_found", "Emergency event not found.", 404)
    _require_site(ctx, event.location_id)
    return _build_event_dict(db, event)


def list_roll_call(
    db: Session,
    ctx: AuthContext,
    emergency_id: int,
    search: Optional[str] = None,
) -> List[Dict[str, Any]]:
    _require_read(ctx)
    event = db.query(EmergencyEvent).filter(EmergencyEvent.id == emergency_id).first()
    if not event:
        raise EmergencyRollCallError("not_found", "Emergency event not found.", 404)
    _require_site(ctx, event.location_id)
    query = (
        db.query(EmergencyRollCallEntry)
        .options(joinedload(EmergencyRollCallEntry.visit))
        .filter(EmergencyRollCallEntry.emergency_event_id == emergency_id)
    )
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                EmergencyRollCallEntry.snapshot_visitor_name.ilike(term),
                EmergencyRollCallEntry.snapshot_company.ilike(term),
                EmergencyRollCallEntry.snapshot_host_name.ilike(term),
                EmergencyRollCallEntry.snapshot_registration_reference.ilike(term),
                EmergencyRollCallEntry.snapshot_badge_number.ilike(term),
                EmergencyRollCallEntry.snapshot_mobile.ilike(term),
            )
        )
    entries = query.order_by(EmergencyRollCallEntry.snapshot_visitor_name).all()
    return [_build_entry_dict(db, e) for e in entries]


def get_roll_call_entry_detail(db: Session, ctx: AuthContext, emergency_id: int, entry_id: int) -> Dict[str, Any]:
    _require_read(ctx)
    event = db.query(EmergencyEvent).filter(EmergencyEvent.id == emergency_id).first()
    if not event:
        raise EmergencyRollCallError("not_found", "Emergency event not found.", 404)
    _require_site(ctx, event.location_id)
    entry = (
        db.query(EmergencyRollCallEntry)
        .options(joinedload(EmergencyRollCallEntry.visit))
        .filter(
            EmergencyRollCallEntry.id == entry_id,
            EmergencyRollCallEntry.emergency_event_id == emergency_id,
        )
        .first()
    )
    if not entry:
        raise EmergencyRollCallError("not_found", "Roll-call entry not found.", 404)
    detail = _build_entry_dict(db, entry)
    visit = entry.visit
    if visit:
        detail["expected_duration_minutes"] = visit.expected_duration_minutes
    actions = (
        db.query(EmergencyRollCallAction)
        .filter(EmergencyRollCallAction.roll_call_entry_id == entry_id)
        .order_by(EmergencyRollCallAction.created_at)
        .all()
    )
    detail["action_history"] = [
        {
            "id": a.id,
            "old_status": a.old_status,
            "new_status": a.new_status,
            "actor_email": a.actor_email,
            "comment": a.comment,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in actions
    ]
    return detail


def start_emergency(
    db: Session,
    ctx: AuthContext,
    location_id: int,
    reason: str,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    _require_start(ctx)
    _require_site(ctx, location_id)
    loc = db.query(Location).filter(Location.id == location_id, Location.is_active.is_(True)).first()
    if not loc:
        raise EmergencyRollCallError("invalid_location", "Location not found or inactive.", 404)

    reason_val = reason.upper()
    if reason_val not in (EmergencyReason.EMERGENCY.value, EmergencyReason.EVACUATION_DRILL.value, EmergencyReason.OTHER.value):
        raise EmergencyRollCallError("invalid_reason", "Invalid emergency reason.")
    if reason_val == EmergencyReason.OTHER.value and not (notes and notes.strip()):
        raise EmergencyRollCallError("notes_required", "Notes are required when reason is OTHER.")

    existing = get_active_emergency_for_location(db, location_id)
    if existing:
        raise EmergencyRollCallError(
            "EMERGENCY_ALREADY_ACTIVE",
            "An active emergency roll-call already exists for this location.",
            409,
        )

    onsite_visits = (
        db.query(Visit)
        .options(
            joinedload(Visit.visitor).joinedload(Visitor.visitor_type),
            joinedload(Visit.badges),
        )
        .filter(Visit.location_id == location_id, Visit.status == VisitStatus.ONSITE.value)
        .all()
    )

    event = EmergencyEvent(
        location_id=location_id,
        status=EmergencyEventStatus.ACTIVE.value,
        started_by_user_id=ctx.user_id,
        reason=reason_val,
        notes=notes.strip() if notes else None,
        visitor_snapshot_count=len(onsite_visits),
    )
    db.add(event)
    db.flush()

    for visit in onsite_visits:
        visitor = visit.visitor
        visitor_type_name = None
        if visitor and visitor.visitor_type:
            visitor_type_name = visitor.visitor_type.name
        entry = EmergencyRollCallEntry(
            emergency_event_id=event.id,
            visit_id=visit.id,
            visitor_id=visit.visitor_id,
            snapshot_visitor_name=visitor.full_name if visitor else "Unknown",
            snapshot_company=visitor.company if visitor else None,
            snapshot_visitor_type=visitor_type_name,
            snapshot_host_name=visit.host_name,
            snapshot_mobile=visitor.phone if visitor else None,
            snapshot_registration_reference=visit.registration_reference,
            snapshot_badge_number=_active_badge_number(visit),
            snapshot_checked_in_at=visit.checked_in_at,
            status=RollCallEntryStatus.UNACCOUNTED.value,
        )
        db.add(entry)

    AuditService(db).record(
        action="EMERGENCY_STARTED",
        entity_type="emergency_event",
        entity_id=str(event.id),
        actor_id=ctx.user_id,
        actor_email=ctx.email,
        location_id=location_id,
        after_value={"visitor_snapshot_count": len(onsite_visits), "reason": reason_val},
    )
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        from sqlalchemy.exc import IntegrityError
        if isinstance(exc, IntegrityError) or (exc.__context__ and isinstance(exc.__context__, IntegrityError)):
            existing = get_active_emergency_for_location(db, location_id)
            if existing:
                raise EmergencyRollCallError(
                    "EMERGENCY_ALREADY_ACTIVE",
                    "An active emergency roll-call already exists for this location.",
                    409,
                )
        raise
    db.refresh(event)
    return _build_event_dict(db, event)


def update_roll_call_status(
    db: Session,
    ctx: AuthContext,
    emergency_id: int,
    entry_id: int,
    new_status: str,
    comment: Optional[str] = None,
    expected_version: Optional[int] = None,
) -> Dict[str, Any]:
    _require_rollcall(ctx)
    event = db.query(EmergencyEvent).filter(EmergencyEvent.id == emergency_id).first()
    if not event:
        raise EmergencyRollCallError("not_found", "Emergency event not found.", 404)
    _require_site(ctx, event.location_id)
    if event.status != EmergencyEventStatus.ACTIVE.value:
        raise EmergencyRollCallError("EMERGENCY_ALREADY_CLOSED", "Cannot update roll-call on a closed emergency.", 409)

    status_val = new_status.upper()
    allowed = {s.value for s in RollCallEntryStatus}
    if status_val not in allowed:
        raise EmergencyRollCallError("invalid_status", "Invalid roll-call status.")

    entry = (
        db.query(EmergencyRollCallEntry)
        .options(joinedload(EmergencyRollCallEntry.visit))
        .filter(
            EmergencyRollCallEntry.id == entry_id,
            EmergencyRollCallEntry.emergency_event_id == emergency_id,
        )
        .first()
    )
    if not entry:
        raise EmergencyRollCallError("not_found", "Roll-call entry not found.", 404)

    if expected_version is not None and entry.version != expected_version:
        raise EmergencyRollCallError(
            "STALE_ROLLCALL_UPDATE",
            "This roll-call entry was updated by another user. Refresh and try again.",
            409,
        )

    old_status = entry.status
    if old_status == status_val:
        return _build_entry_dict(db, entry)

    now = datetime.now(timezone.utc)
    result = db.execute(
        update(EmergencyRollCallEntry)
        .where(
            EmergencyRollCallEntry.id == entry_id,
            EmergencyRollCallEntry.emergency_event_id == emergency_id,
            EmergencyRollCallEntry.version == entry.version,
        )
        .values(
            status=status_val,
            status_updated_at=now,
            status_updated_by_user_id=ctx.user_id,
            comment=comment.strip() if comment else entry.comment,
            version=entry.version + 1,
        )
    )
    if result.rowcount == 0:
        raise EmergencyRollCallError(
            "STALE_ROLLCALL_UPDATE",
            "This roll-call entry was updated by another user. Refresh and try again.",
            409,
        )

    action = EmergencyRollCallAction(
        emergency_event_id=emergency_id,
        roll_call_entry_id=entry_id,
        old_status=old_status,
        new_status=status_val,
        actor_user_id=ctx.user_id,
        actor_email=ctx.email,
        comment=comment.strip() if comment else None,
    )
    db.add(action)

    AuditService(db).record(
        action="EMERGENCY_ROLLCALL_STATUS_UPDATED",
        entity_type="emergency_roll_call_entry",
        entity_id=str(entry_id),
        actor_id=ctx.user_id,
        actor_email=ctx.email,
        location_id=event.location_id,
        before_value={"status": old_status},
        after_value={"status": status_val, "comment": comment},
    )
    db.commit()
    db.refresh(entry)
    return _build_entry_dict(db, entry)


def close_emergency(
    db: Session,
    ctx: AuthContext,
    emergency_id: int,
    closure_comment: Optional[str] = None,
    confirm_unresolved: bool = False,
) -> Dict[str, Any]:
    _require_close(ctx)
    event = db.query(EmergencyEvent).filter(EmergencyEvent.id == emergency_id).first()
    if not event:
        raise EmergencyRollCallError("not_found", "Emergency event not found.", 404)
    _require_site(ctx, event.location_id)
    if event.status == EmergencyEventStatus.CLOSED.value:
        return _build_event_dict(db, event)

    if event.status != EmergencyEventStatus.ACTIVE.value:
        raise EmergencyRollCallError("invalid_state", "Emergency is not active.", 409)

    counts = _count_entries_by_status(db, emergency_id)
    unresolved = counts["unaccounted"] + counts["not_located"]
    if unresolved > 0:
        if not confirm_unresolved:
            raise EmergencyRollCallError(
                "unresolved_visitors",
                f"{unresolved} visitor(s) remain unaccounted or not located. Confirmation required.",
                409,
            )
        if not closure_comment or not closure_comment.strip():
            raise EmergencyRollCallError("closure_comment_required", "Closure comment is required for unresolved emergencies.")

    now = datetime.now(timezone.utc)
    result = db.execute(
        update(EmergencyEvent)
        .where(
            EmergencyEvent.id == emergency_id,
            EmergencyEvent.status == EmergencyEventStatus.ACTIVE.value,
        )
        .values(
            status=EmergencyEventStatus.CLOSED.value,
            closed_at=now,
            closed_by_user_id=ctx.user_id,
            closure_comment=closure_comment.strip() if closure_comment else None,
        )
    )
    if result.rowcount == 0:
        db.refresh(event)
        if event.status == EmergencyEventStatus.CLOSED.value:
            return _build_event_dict(db, event)
        raise EmergencyRollCallError("invalid_state", "Emergency state changed. Refresh and try again.", 409)

    audit_action = "EMERGENCY_CLOSED"
    if unresolved > 0:
        audit_action = "EMERGENCY_CLOSED_WITH_UNRESOLVED_VISITORS"

    AuditService(db).record(
        action=audit_action,
        entity_type="emergency_event",
        entity_id=str(emergency_id),
        actor_id=ctx.user_id,
        actor_email=ctx.email,
        location_id=event.location_id,
        after_value={"closure_comment": closure_comment, "unresolved": unresolved},
    )
    db.commit()
    event = db.query(EmergencyEvent).filter(EmergencyEvent.id == emergency_id).first()
    return _build_event_dict(db, event)
