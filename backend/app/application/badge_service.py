"""Visitor badge issuance and lifecycle."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import func, update
from sqlalchemy.orm import Session, joinedload

from app.application.audit_service import AuditService
from app.application.auth_service import AuthContext
from app.application.site_scope_service import can_access_location
from app.domain.enums import BadgeStatus, Permission, VisitStatus, role_has_permission
from app.domain.models import Location, Visit, Visitor, VisitorBadge


class BadgeError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _require_issue(ctx: AuthContext) -> None:
    if not role_has_permission(ctx.role, Permission.BADGE_ISSUE):
        raise BadgeError("forbidden", "Permission denied.", 403)


def _require_read(ctx: AuthContext) -> None:
    if not role_has_permission(ctx.role, Permission.BADGE_READ):
        raise BadgeError("forbidden", "Permission denied.", 403)


def _require_site(ctx: AuthContext, location_id: int) -> None:
    if not can_access_location(ctx, location_id):
        raise BadgeError("LOCATION_ACCESS_DENIED", "You do not have access to this site.", 403)


def generate_badge_number(db: Session, location_code: str) -> str:
    prefix = f"{location_code}-V-"
    count = db.query(func.count(VisitorBadge.id)).filter(
        VisitorBadge.badge_number.like(f"{prefix}%")
    ).scalar() or 0
    seq = count + 1
    for attempt in range(100):
        number = f"{prefix}{seq:05d}"
        exists = db.query(VisitorBadge.id).filter(VisitorBadge.badge_number == number).first()
        if not exists:
            return number
        seq += 1
    raise BadgeError("badge_number_failed", "Unable to generate badge number.", 500)


def _load_visit(db: Session, visit_id: int) -> Optional[Visit]:
    return (
        db.query(Visit)
        .options(
            joinedload(Visit.visitor).joinedload(Visitor.visitor_type),
            joinedload(Visit.location),
            joinedload(Visit.badges),
        )
        .filter(Visit.id == visit_id)
        .first()
    )


def _active_badge(visit: Visit) -> Optional[VisitorBadge]:
    for badge in visit.badges:
        if badge.status == BadgeStatus.ACTIVE.value:
            return badge
    return None


def _build_badge_dict(badge: VisitorBadge, visit: Visit) -> Dict[str, Any]:
    visitor = visit.visitor
    location = visit.location
    visitor_type_name = visitor.visitor_type.name if visitor and visitor.visitor_type else None
    return {
        "id": badge.id,
        "visit_id": visit.id,
        "badge_number": badge.badge_number,
        "status": badge.status,
        "issued_at": badge.issued_at.isoformat() if badge.issued_at else None,
        "printed_at": badge.printed_at.isoformat() if badge.printed_at else None,
        "print_count": badge.print_count,
        "expires_at": badge.expires_at.isoformat() if badge.expires_at else None,
        "visitor_name": visitor.full_name if visitor else "",
        "company": visitor.company if visitor else None,
        "visitor_type": visitor_type_name,
        "host_name": visit.host_name,
        "site_name": location.name if location else "",
        "site_code": location.code if location else None,
        "site_city": location.city if location else None,
        "registration_reference": visit.registration_reference,
        "scheduled_start": visit.scheduled_start.isoformat() if visit.scheduled_start else None,
        "visit_date": visit.scheduled_start.isoformat() if visit.scheduled_start else (
            visit.checked_in_at.isoformat() if visit.checked_in_at else None
        ),
    }


def issue_badge(db: Session, ctx: AuthContext, visit_id: int) -> Dict[str, Any]:
    _require_issue(ctx)
    visit = _load_visit(db, visit_id)
    if not visit:
        raise BadgeError("VISIT_NOT_FOUND", "Visit not found.", 404)
    _require_site(ctx, visit.location_id)

    if visit.status != VisitStatus.ONSITE.value:
        raise BadgeError("INVALID_VISIT_STATE", "Badge can only be issued for onsite visitors.", 409)

    existing = _active_badge(visit)
    if existing:
        return _build_badge_dict(existing, visit)

    location = visit.location or db.query(Location).filter(Location.id == visit.location_id).first()
    if not location:
        raise BadgeError("invalid_location", "Location not found.")

    now = datetime.now(timezone.utc)
    expires_at = visit.scheduled_end
    if not expires_at and visit.checked_in_at and visit.expected_duration_minutes:
        from datetime import timedelta
        checked_in = visit.checked_in_at
        if checked_in.tzinfo is None:
            checked_in = checked_in.replace(tzinfo=timezone.utc)
        expires_at = checked_in + timedelta(minutes=visit.expected_duration_minutes)

    badge = VisitorBadge(
        visit_id=visit_id,
        badge_number=generate_badge_number(db, location.code),
        status=BadgeStatus.ACTIVE.value,
        issued_by_user_id=ctx.user_id,
        expires_at=expires_at,
        print_count=0,
    )
    db.add(badge)
    db.flush()

    audit = AuditService(db)
    audit.record(
        action="BADGE_ISSUED",
        entity_type="visitor_badge",
        entity_id=str(badge.id),
        actor_id=ctx.user_id,
        actor_email=ctx.email,
        location_id=visit.location_id,
        after_value={"badge_number": badge.badge_number, "visit_id": visit_id},
    )

    db.commit()
    db.refresh(badge)
    return _build_badge_dict(badge, _load_visit(db, visit_id) or visit)


def record_print(db: Session, ctx: AuthContext, visit_id: int, reprint: bool = False) -> Dict[str, Any]:
    _require_issue(ctx)
    visit = _load_visit(db, visit_id)
    if not visit:
        raise BadgeError("VISIT_NOT_FOUND", "Visit not found.", 404)
    _require_site(ctx, visit.location_id)

    badge = _active_badge(visit)
    if not badge:
        raise BadgeError("BADGE_NOT_FOUND", "No active badge for this visit.", 404)

    now = datetime.now(timezone.utc)
    badge.printed_at = now
    badge.print_count = (badge.print_count or 0) + 1

    audit = AuditService(db)
    action = "BADGE_REPRINTED" if reprint or badge.print_count > 1 else "BADGE_PRINTED"
    audit.record(
        action=action,
        entity_type="visitor_badge",
        entity_id=str(badge.id),
        actor_id=ctx.user_id,
        actor_email=ctx.email,
        location_id=visit.location_id,
        after_value={"print_count": badge.print_count},
    )

    db.commit()
    return _build_badge_dict(badge, visit)


def get_badge_for_visit(db: Session, ctx: AuthContext, visit_id: int) -> Dict[str, Any]:
    _require_read(ctx)
    visit = _load_visit(db, visit_id)
    if not visit:
        raise BadgeError("VISIT_NOT_FOUND", "Visit not found.", 404)
    _require_site(ctx, visit.location_id)

    badge = _active_badge(visit)
    if not badge:
        latest = (
            db.query(VisitorBadge)
            .filter(VisitorBadge.visit_id == visit_id)
            .order_by(VisitorBadge.created_at.desc())
            .first()
        )
        if not latest:
            raise BadgeError("BADGE_NOT_FOUND", "No badge for this visit.", 404)
        return _build_badge_dict(latest, visit)
    return _build_badge_dict(badge, visit)


def expire_badges_for_visit(db: Session, visit_id: int, actor_id: Optional[int] = None, actor_email: Optional[str] = None) -> None:
    active = (
        db.query(VisitorBadge)
        .filter(VisitorBadge.visit_id == visit_id, VisitorBadge.status == BadgeStatus.ACTIVE.value)
        .all()
    )
    if not active:
        return

    db.execute(
        update(VisitorBadge)
        .where(VisitorBadge.visit_id == visit_id, VisitorBadge.status == BadgeStatus.ACTIVE.value)
        .values(status=BadgeStatus.EXPIRED.value)
    )

    audit = AuditService(db)
    for badge in active:
        audit.record(
            action="BADGE_EXPIRED",
            entity_type="visitor_badge",
            entity_id=str(badge.id),
            actor_id=actor_id,
            actor_email=actor_email,
            after_value={"badge_number": badge.badge_number},
        )
