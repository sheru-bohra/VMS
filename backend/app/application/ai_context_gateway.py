"""Allowlisted read tools and context assembly for AI."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session, joinedload

from app.application.analytics_service import get_dashboard
from app.application.auth_service import AuthContext
from app.application.ai_data_redaction_service import redact_dict
from app.application.site_scope_service import get_allowed_location_ids
from app.application.timezone_service import get_location_day_bounds
from app.core.config import settings
from app.domain.enums import (
    ComplianceStatus,
    Permission,
    SecurityClearanceStatus,
    VisitStatus,
    role_has_permission,
)
from app.domain.models import EmergencyEvent, Location, Visit, Visitor, VisitorType


class AIContextError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _resolve_locations(db: Session, ctx: AuthContext, location_id: Optional[int]) -> List[int]:
    allowed = get_allowed_location_ids(ctx, db, location_id)
    if allowed is None:
        if location_id is not None:
            if not role_has_permission(ctx.role, Permission.AI_OPERATIONAL_READ):
                raise AIContextError("forbidden", "Permission denied.", 403)
            return [location_id]
        locs = [r[0] for r in db.query(Location.id).filter(Location.is_active.is_(True)).all()]
        return locs
    if not allowed:
        raise AIContextError("forbidden", "No accessible locations.", 403)
    if location_id is not None and location_id not in allowed:
        raise AIContextError("forbidden", "Location outside your access scope.", 403)
    return allowed if location_id is None else [location_id]


def _visit_brief(visit: Visit, include_name: bool = True) -> Dict[str, Any]:
    visitor = visit.visitor
    return {
        "registration_reference": visit.registration_reference,
        "visitor_name": visitor.full_name if visitor and include_name else None,
        "company": visitor.company if visitor else None,
        "visitor_type": visitor.visitor_type.name if visitor and visitor.visitor_type else None,
        "location_name": visit.location.name if visit.location else None,
        "status": visit.status,
        "purpose": visit.purpose,
        "checked_in_at": visit.checked_in_at.isoformat() if visit.checked_in_at else None,
        "expected_duration_minutes": visit.expected_duration_minutes,
        "security_status": visit.security_clearance_status,
        "compliance_status": visit.compliance_status,
    }


def get_operational_summary(db: Session, ctx: AuthContext, location_ids: List[int]) -> Dict[str, Any]:
    kpis = {}
    for loc_id in location_ids:
        loc = db.query(Location).filter(Location.id == loc_id).first()
        start, end = get_location_day_bounds(loc.timezone if loc else None)
        expected = (
            db.query(Visit)
            .filter(Visit.location_id == loc_id, Visit.created_at >= start, Visit.created_at < end)
            .count()
        )
        onsite = db.query(Visit).filter(Visit.location_id == loc_id, Visit.status == VisitStatus.ONSITE.value).count()
        pending = db.query(Visit).filter(Visit.location_id == loc_id, Visit.status == VisitStatus.PENDING_APPROVAL.value).count()
        kpis[loc.name if loc else str(loc_id)] = {
            "expected_today": expected,
            "onsite_now": onsite,
            "pending_approval": pending,
        }
    emergencies = (
        db.query(EmergencyEvent)
        .filter(EmergencyEvent.location_id.in_(location_ids), EmergencyEvent.status == "ACTIVE")
        .count()
    )
    return {"locations": kpis, "active_emergencies": emergencies}


def get_onsite_visitors(db: Session, location_ids: List[int], limit: int = 50) -> List[Dict[str, Any]]:
    visits = (
        db.query(Visit)
        .options(joinedload(Visit.visitor).joinedload(Visitor.visitor_type), joinedload(Visit.location))
        .filter(Visit.location_id.in_(location_ids), Visit.status == VisitStatus.ONSITE.value)
        .limit(min(limit, settings.ai_max_context_records))
        .all()
    )
    return [_visit_brief(v) for v in visits]


def get_pending_approvals(db: Session, location_ids: List[int], limit: int = 50) -> List[Dict[str, Any]]:
    visits = (
        db.query(Visit)
        .options(joinedload(Visit.visitor), joinedload(Visit.location))
        .filter(Visit.location_id.in_(location_ids), Visit.status == VisitStatus.PENDING_APPROVAL.value)
        .order_by(Visit.created_at.asc())
        .limit(min(limit, settings.ai_max_context_records))
        .all()
    )
    return [_visit_brief(v) for v in visits]


def get_security_review_summary(db: Session, location_ids: List[int]) -> Dict[str, Any]:
    review = (
        db.query(Visit)
        .filter(
            Visit.location_id.in_(location_ids),
            Visit.security_clearance_status == SecurityClearanceStatus.REVIEW.value,
        )
        .count()
    )
    blocked = (
        db.query(Visit)
        .filter(
            Visit.location_id.in_(location_ids),
            Visit.security_clearance_status == SecurityClearanceStatus.BLOCKED.value,
        )
        .count()
    )
    return {"review_count": review, "blocked_count": blocked}


def get_compliance_attention(db: Session, location_ids: List[int], limit: int = 50) -> List[Dict[str, Any]]:
    visits = (
        db.query(Visit)
        .options(joinedload(Visit.visitor), joinedload(Visit.location))
        .filter(
            Visit.location_id.in_(location_ids),
            Visit.compliance_status.in_([
                ComplianceStatus.REVIEW_REQUIRED.value,
                ComplianceStatus.NON_COMPLIANT.value,
                ComplianceStatus.EXPIRING.value,
            ]),
        )
        .limit(min(limit, settings.ai_max_context_records))
        .all()
    )
    return [_visit_brief(v) for v in visits]


def get_active_emergencies(db: Session, location_ids: List[int]) -> List[Dict[str, Any]]:
    events = (
        db.query(EmergencyEvent)
        .filter(EmergencyEvent.location_id.in_(location_ids), EmergencyEvent.status == "ACTIVE")
        .all()
    )
    out = []
    for e in events:
        loc = db.query(Location).filter(Location.id == e.location_id).first()
        out.append({
            "id": e.id,
            "location_name": loc.name if loc else None,
            "reason": e.reason,
            "visitor_snapshot_count": e.visitor_snapshot_count,
            "started_at": e.started_at.isoformat() if e.started_at else None,
        })
    return out


def get_overstays(db: Session, location_ids: List[int]) -> List[Dict[str, Any]]:
    now = datetime.now(timezone.utc)
    visits = (
        db.query(Visit)
        .options(joinedload(Visit.visitor), joinedload(Visit.location))
        .filter(Visit.location_id.in_(location_ids), Visit.status == VisitStatus.ONSITE.value)
        .all()
    )
    out = []
    for v in visits:
        if v.checked_in_at and v.expected_duration_minutes:
            checked = v.checked_in_at
            if checked.tzinfo is None:
                checked = checked.replace(tzinfo=timezone.utc)
            overdue_min = int((now - checked).total_seconds() / 60) - v.expected_duration_minutes
            if overdue_min >= settings.ai_overstay_attention_minutes:
                brief = _visit_brief(v)
                brief["overdue_minutes"] = overdue_min
                out.append(brief)
    return out[:settings.ai_max_context_records]


def get_management_summary(db: Session, ctx: AuthContext, location_id: Optional[int]) -> Dict[str, Any]:
    if not role_has_permission(ctx.role, Permission.AI_MANAGEMENT_READ):
        raise AIContextError("forbidden", "You don't have access to management analytics.", 403)
    return get_dashboard(db, ctx, period="today", location_id=location_id)


def build_context_for_intent(
    db: Session,
    ctx: AuthContext,
    intent: str,
    location_id: Optional[int] = None,
    question: str = "",
) -> Dict[str, Any]:
    location_ids = _resolve_locations(db, ctx, location_id)
    loc_names = [
        db.query(Location).filter(Location.id == lid).first().name
        for lid in location_ids
    ]
    ctx_data: Dict[str, Any] = {
        "intent": intent,
        "location_scope": loc_names,
        "location_ids": location_ids,
        "role": ctx.role.value,
    }

    if intent in ("MANAGEMENT_SUMMARY", "LOCATION_COMPARISON", "TREND_QUERY"):
        if not role_has_permission(ctx.role, Permission.AI_MANAGEMENT_READ):
            raise AIContextError("forbidden", "You don't have access to management analytics.", 403)
        dash = get_dashboard(db, ctx, period="last_7_days" if intent == "TREND_QUERY" else "today", location_id=location_id)
        ctx_data["management_dashboard"] = {
            "kpis": dash.get("kpis"),
            "visitor_trend": dash.get("visitor_trend", [])[:14],
            "locations": dash.get("locations", []),
            "range": dash.get("range"),
        }
        return redact_dict(ctx_data)

    ctx_data["operational_summary"] = get_operational_summary(db, ctx, location_ids)
    ctx_data["onsite_visitors"] = get_onsite_visitors(db, location_ids)
    ctx_data["pending_approvals"] = get_pending_approvals(db, location_ids)
    ctx_data["security_summary"] = get_security_review_summary(db, location_ids)
    ctx_data["compliance_attention"] = get_compliance_attention(db, location_ids)
    ctx_data["active_emergencies"] = get_active_emergencies(db, location_ids)
    ctx_data["overstays"] = get_overstays(db, location_ids)

    if "history" in question.lower():
        # visitor name extraction is minimal — use last word chunk as hint
        parts = [p for p in question.replace("?", "").split() if len(p) > 2]
        if parts:
            hint = parts[-1]
            visits = (
                db.query(Visit)
                .join(Visitor)
                .options(joinedload(Visit.visitor), joinedload(Visit.location))
                .filter(Visit.location_id.in_(location_ids), Visitor.full_name.ilike(f"%{hint}%"))
                .order_by(Visit.created_at.desc())
                .limit(20)
                .all()
            )
            ctx_data["visitor_history"] = [_visit_brief(v) for v in visits]

    return redact_dict(ctx_data)
