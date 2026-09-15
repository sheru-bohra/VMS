"""Security review queue and resolution."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session, joinedload

from app.application.audit_service import AuditService
from app.application.auth_service import AuthContext
from app.application.site_scope_service import apply_location_scope, can_access_location
from app.domain.enums import (
    Permission,
    SecurityClearanceStatus,
    SecurityOutcome,
    SecurityResolution,
    role_has_permission,
)
from app.domain.models import Location, SecurityScreening, Visit, Visitor, VisitorType


class SecurityReviewError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _require_read(ctx: AuthContext) -> None:
    if not role_has_permission(ctx.role, Permission.SECURITY_SCREENING_READ):
        raise SecurityReviewError("forbidden", "Permission denied.", 403)


def _require_resolve(ctx: AuthContext) -> None:
    if not role_has_permission(ctx.role, Permission.SECURITY_SCREENING_RESOLVE):
        raise SecurityReviewError("forbidden", "Permission denied.", 403)


def _build_visit_review(db: Session, visit: Visit) -> Dict[str, Any]:
    visitor = visit.visitor
    location = visit.location
    vt_name = visitor.visitor_type.name if visitor and visitor.visitor_type else None
    latest = (
        db.query(SecurityScreening)
        .filter(SecurityScreening.visit_id == visit.id)
        .order_by(SecurityScreening.screened_at.desc())
        .first()
    )
    signals: List[str] = []
    if latest and latest.signals_json:
        try:
            signals = json.loads(latest.signals_json)
        except json.JSONDecodeError:
            signals = []
    return {
        "visit_id": visit.id,
        "registration_reference": visit.registration_reference,
        "status": visit.status,
        "source": visit.source,
        "security_status": visit.security_clearance_status,
        "visitor_name": visitor.full_name if visitor else "",
        "visitor_mobile": visitor.phone if visitor else None,
        "visitor_email": visitor.email if visitor else None,
        "company": visitor.company if visitor else None,
        "visitor_type": vt_name,
        "host_name": visit.host_name,
        "site_name": location.name if location else "",
        "site_id": visit.location_id,
        "purpose": visit.purpose,
        "screening_outcome": latest.outcome if latest else None,
        "match_confidence": latest.highest_match_confidence if latest else None,
        "reason_summary": latest.reason_summary if latest else None,
        "signals": signals,
        "screening_id": latest.id if latest else None,
        "resolved": bool(latest and latest.resolution),
        "resolution": latest.resolution if latest else None,
        "screened_at": latest.screened_at.isoformat() if latest and latest.screened_at else None,
    }


def list_security_reviews(
    db: Session,
    ctx: AuthContext,
    tab: Optional[str] = None,
    search: Optional[str] = None,
    site: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[List[Dict[str, Any]], int, int, int]:
    _require_read(ctx)
    query = (
        db.query(Visit)
        .options(
            joinedload(Visit.visitor).joinedload(Visitor.visitor_type),
            joinedload(Visit.location),
        )
    )
    query = apply_location_scope(query, ctx, db, site)

    if tab == "BLOCKED":
        query = query.filter(Visit.security_clearance_status == SecurityClearanceStatus.BLOCKED.value)
    elif tab == "RESOLVED":
        query = query.join(SecurityScreening).filter(SecurityScreening.resolution.isnot(None)).distinct()
    else:
        query = query.filter(Visit.security_clearance_status == SecurityClearanceStatus.REVIEW.value)

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.join(Visitor, Visit.visitor_id == Visitor.id).filter(
            Visitor.full_name.ilike(term) | Visitor.company.ilike(term) | Visit.registration_reference.ilike(term)
        )

    review_count = apply_location_scope(
        db.query(Visit).filter(Visit.security_clearance_status == SecurityClearanceStatus.REVIEW.value),
        ctx,
        db,
        site,
    ).count()
    blocked_count = apply_location_scope(
        db.query(Visit).filter(Visit.security_clearance_status == SecurityClearanceStatus.BLOCKED.value),
        ctx,
        db,
        site,
    ).count()

    total = query.count()
    visits = query.order_by(Visit.updated_at.desc()).offset(offset).limit(limit).all()
    return [_build_visit_review(db, v) for v in visits], total, review_count, blocked_count


def get_security_review(db: Session, ctx: AuthContext, visit_id: int) -> Dict[str, Any]:
    _require_read(ctx)
    visit = (
        db.query(Visit)
        .options(
            joinedload(Visit.visitor).joinedload(Visitor.visitor_type),
            joinedload(Visit.location),
        )
        .filter(Visit.id == visit_id)
        .first()
    )
    if not visit:
        raise SecurityReviewError("not_found", "Visit not found.", 404)
    if not can_access_location(ctx, visit.location_id):
        raise SecurityReviewError("forbidden", "Permission denied.", 403)
    return _build_visit_review(db, visit)


def resolve_clear(db: Session, ctx: AuthContext, visit_id: int, comment: Optional[str] = None) -> Dict[str, Any]:
    _require_resolve(ctx)
    visit = db.query(Visit).filter(Visit.id == visit_id).first()
    if not visit:
        raise SecurityReviewError("not_found", "Visit not found.", 404)
    if not can_access_location(ctx, visit.location_id):
        raise SecurityReviewError("forbidden", "Permission denied.", 403)
    latest = (
        db.query(SecurityScreening)
        .filter(SecurityScreening.visit_id == visit_id)
        .order_by(SecurityScreening.screened_at.desc())
        .first()
    )
    if not latest:
        raise SecurityReviewError("no_screening", "No screening record found.", 400)
    now = datetime.now(timezone.utc)
    latest.resolved_at = now
    latest.resolved_by_user_id = ctx.user_id
    latest.resolution = SecurityResolution.CLEAR_VISITOR.value
    latest.resolution_comment = comment
    visit.security_clearance_status = SecurityClearanceStatus.CLEAR.value
    AuditService(db).record(
        action="SECURITY_REVIEW_CLEARED",
        entity_type="visit",
        entity_id=str(visit_id),
        actor_id=ctx.user_id,
        actor_email=ctx.email,
        location_id=visit.location_id,
        after_value={"resolution": SecurityResolution.CLEAR_VISITOR.value},
    )
    db.commit()
    return get_security_review(db, ctx, visit_id)


def resolve_block(db: Session, ctx: AuthContext, visit_id: int, comment: str) -> Dict[str, Any]:
    _require_resolve(ctx)
    if not comment or not comment.strip():
        raise SecurityReviewError("comment_required", "A comment is required to keep blocked.")
    visit = db.query(Visit).filter(Visit.id == visit_id).first()
    if not visit:
        raise SecurityReviewError("not_found", "Visit not found.", 404)
    if not can_access_location(ctx, visit.location_id):
        raise SecurityReviewError("forbidden", "Permission denied.", 403)
    latest = (
        db.query(SecurityScreening)
        .filter(SecurityScreening.visit_id == visit_id)
        .order_by(SecurityScreening.screened_at.desc())
        .first()
    )
    if not latest:
        raise SecurityReviewError("no_screening", "No screening record found.", 400)
    now = datetime.now(timezone.utc)
    latest.resolved_at = now
    latest.resolved_by_user_id = ctx.user_id
    latest.resolution = SecurityResolution.KEEP_BLOCKED.value
    latest.resolution_comment = comment.strip()
    visit.security_clearance_status = SecurityClearanceStatus.BLOCKED.value
    AuditService(db).record(
        action="SECURITY_REVIEW_BLOCKED",
        entity_type="visit",
        entity_id=str(visit_id),
        actor_id=ctx.user_id,
        actor_email=ctx.email,
        location_id=visit.location_id,
        after_value={"resolution": SecurityResolution.KEEP_BLOCKED.value},
    )
    db.commit()
    return get_security_review(db, ctx, visit_id)
