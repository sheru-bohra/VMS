"""Deterministic visitor intelligence and AI insight persistence."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.application.audit_service import AuditService
from app.application.auth_service import AuthContext
from app.application.site_scope_service import get_allowed_location_ids
from app.core.config import settings
from app.domain.enums import ComplianceStatus, Permission, SecurityClearanceStatus, VisitStatus, role_has_permission
from app.domain.models import AIInsight, Location, SecurityScreening, Visit, Visitor, VisitorType

RULES_VERSION = "v1"


class IntelligenceError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _upsert_insight(
    db: Session,
    fingerprint: str,
    insight_type: str,
    priority: str,
    title: str,
    summary: str,
    evidence: Dict[str, Any],
    location_id: Optional[int] = None,
    visit_id: Optional[int] = None,
    visitor_id: Optional[int] = None,
) -> Optional[AIInsight]:
    existing = db.query(AIInsight).filter(AIInsight.fingerprint == fingerprint).first()
    if existing and existing.status == "DISMISSED":
        return None
    if existing:
        existing.title = title
        existing.summary = summary
        existing.evidence_json = json.dumps(evidence)
        existing.priority = priority
        existing.generated_at = datetime.now(timezone.utc)
        existing.status = "ACTIVE"
        db.flush()
        return existing
    insight = AIInsight(
        insight_type=insight_type,
        location_id=location_id,
        visit_id=visit_id,
        visitor_id=visitor_id,
        status="ACTIVE",
        priority=priority,
        title=title,
        summary=summary,
        evidence_json=json.dumps(evidence),
        fingerprint=fingerprint,
        rules_version=RULES_VERSION,
        generated_at=datetime.now(timezone.utc),
    )
    db.add(insight)
    db.flush()
    AuditService(db).record(
        action="AI_INSIGHT_GENERATED",
        entity_type="ai_insight",
        entity_id=str(insight.id),
        metadata={"insight_type": insight_type, "fingerprint": fingerprint},
        location_id=location_id,
    )
    return insight


def generate_insights_for_locations(db: Session, location_ids: List[int]) -> int:
    now = datetime.now(timezone.utc)
    created = 0

    # Overstays
    onsite = (
        db.query(Visit)
        .options(joinedload(Visit.visitor), joinedload(Visit.location))
        .filter(Visit.location_id.in_(location_ids), Visit.status == VisitStatus.ONSITE.value)
        .all()
    )
    for v in onsite:
        if not v.checked_in_at or not v.expected_duration_minutes:
            continue
        checked = v.checked_in_at
        if checked.tzinfo is None:
            checked = checked.replace(tzinfo=timezone.utc)
        overdue = int((now - checked).total_seconds() / 60) - v.expected_duration_minutes
        if overdue < settings.ai_overstay_attention_minutes:
            continue
        priority = "URGENT" if overdue >= settings.ai_overstay_urgent_minutes else "ATTENTION"
        bucket = overdue // 30
        fp = f"OVERSTAY:{v.id}:{bucket}"
        evidence = {
            "bullets": [
                f"Expected duration: {v.expected_duration_minutes} minutes",
                f"Overdue by {overdue} minutes",
                f"Visit {v.registration_reference}",
            ],
            "confidence": "CLEAR_EVIDENCE",
        }
        if _upsert_insight(
            db, fp, "OVERSTAY_ATTENTION", priority,
            "Visitor overstayed expected duration",
            f"{v.visitor.full_name if v.visitor else 'Visitor'} is {overdue} minutes beyond expected duration.",
            evidence, v.location_id, v.id, v.visitor_id,
        ):
            created += 1

    # Approval delay
    delay_threshold = timedelta(minutes=settings.ai_approval_delay_minutes)
    pending = (
        db.query(Visit)
        .filter(
            Visit.location_id.in_(location_ids),
            Visit.status == VisitStatus.PENDING_APPROVAL.value,
            Visit.created_at < now - delay_threshold,
        )
        .all()
    )
    if pending:
        by_loc: Dict[int, int] = {}
        for p in pending:
            by_loc[p.location_id] = by_loc.get(p.location_id, 0) + 1
        for loc_id, cnt in by_loc.items():
            fp = f"APPROVAL_DELAY:{loc_id}:{cnt}"
            evidence = {"bullets": [f"{cnt} requests waiting more than {settings.ai_approval_delay_minutes} minutes"], "confidence": "CLEAR_EVIDENCE"}
            if _upsert_insight(
                db, fp, "APPROVAL_DELAY", "ATTENTION",
                "Approval delay",
                f"{cnt} visitor requests have been pending approval for more than {settings.ai_approval_delay_minutes} minutes.",
                evidence, loc_id,
            ):
                created += 1

    # Security review aging
    sec_threshold = timedelta(minutes=settings.ai_security_review_aging_minutes)
    review_visits = (
        db.query(Visit)
        .filter(
            Visit.location_id.in_(location_ids),
            Visit.security_clearance_status == SecurityClearanceStatus.REVIEW.value,
            Visit.updated_at < now - sec_threshold,
        )
        .all()
    )
    if review_visits:
        by_loc: Dict[int, int] = {}
        for rv in review_visits:
            by_loc[rv.location_id] = by_loc.get(rv.location_id, 0) + 1
        for loc_id, cnt in by_loc.items():
            fp = f"SECURITY_REVIEW_AGING:{loc_id}:{cnt}"
            evidence = {"bullets": [f"{cnt} unresolved security reviews"], "confidence": "CLEAR_EVIDENCE"}
            if _upsert_insight(
                db, fp, "SECURITY_REVIEW_AGING", "ATTENTION",
                "Security reviews aging",
                f"{cnt} security reviews remain unresolved for more than {settings.ai_security_review_aging_minutes} minutes.",
                evidence, loc_id,
            ):
                created += 1

    # Compliance attention
    compliance_visits = (
        db.query(Visit)
        .options(joinedload(Visit.visitor))
        .filter(
            Visit.location_id.in_(location_ids),
            Visit.compliance_status.in_([
                ComplianceStatus.REVIEW_REQUIRED.value,
                ComplianceStatus.NON_COMPLIANT.value,
                ComplianceStatus.EXPIRING.value,
            ]),
        )
        .limit(settings.ai_max_context_records)
        .all()
    )
    for cv in compliance_visits:
        fp = f"COMPLIANCE_ATTENTION:{cv.id}:{cv.compliance_status}"
        evidence = {
            "bullets": [f"Status: {cv.compliance_status}", f"Visit {cv.registration_reference}"],
            "confidence": "CLEAR_EVIDENCE",
            "suggested_action": "Review Contractor Compliance",
        }
        if _upsert_insight(
            db, fp, "COMPLIANCE_ATTENTION", "ATTENTION",
            "Compliance attention required",
            f"{cv.visitor.full_name if cv.visitor else 'Visitor'} — compliance status {cv.compliance_status}.",
            evidence, cv.location_id, cv.id, cv.visitor_id,
        ):
            created += 1

    # Repeat visitor (14 days, 5+ visits)
    since = now - timedelta(days=14)
    repeat_rows = (
        db.query(Visitor.id, Visitor.full_name, func.count(Visit.id).label("cnt"))
        .join(Visit)
        .filter(Visit.location_id.in_(location_ids), Visit.created_at >= since)
        .group_by(Visitor.id, Visitor.full_name)
        .having(func.count(Visit.id) >= 5)
        .all()
    )
    for visitor_id, name, cnt in repeat_rows:
        fp = f"REPEAT_VISITOR:{visitor_id}:14d"
        evidence = {"bullets": [f"{cnt} registrations in 14 days"], "confidence": "MULTIPLE_SIGNALS"}
        if _upsert_insight(
            db, fp, "REPEAT_VISITOR", "INFORMATION",
            "Repeat visitor activity",
            f"{name} has registered {cnt} times in the last 14 days.",
            evidence, None, None, visitor_id,
        ):
            created += 1

    # Repeated rejections
    rej_since = now - timedelta(days=30)
    visitors = (
        db.query(Visitor.id, Visitor.full_name)
        .join(Visit)
        .filter(Visit.location_id.in_(location_ids), Visit.created_at >= rej_since)
        .distinct()
        .all()
    )
    for visitor_id, name in visitors:
        recent = (
            db.query(Visit)
            .filter(
                Visit.visitor_id == visitor_id,
                Visit.location_id.in_(location_ids),
                Visit.created_at >= rej_since,
            )
            .order_by(Visit.created_at.desc())
            .limit(5)
            .all()
        )
        if len(recent) < 3:
            continue
        rejected = sum(1 for r in recent if r.status == VisitStatus.REJECTED.value)
        if rejected >= 2:
            fp = f"REPEATED_REJECTIONS:{visitor_id}:{rejected}"
            evidence = {"bullets": [f"{rejected} of last {len(recent)} requests rejected"], "confidence": "CLEAR_EVIDENCE"}
            if _upsert_insight(
                db, fp, "REPEATED_REJECTIONS", "ATTENTION",
                "Repeated visit rejections",
                f"{name}: {rejected} of the last {len(recent)} requests were rejected.",
                evidence, None, None, visitor_id,
            ):
                created += 1

    # Multi-location visitor
    multi = (
        db.query(Visitor.id, Visitor.full_name, func.count(func.distinct(Visit.location_id)).label("loc_cnt"))
        .join(Visit)
        .filter(Visit.location_id.in_(location_ids), Visit.created_at >= now - timedelta(days=30))
        .group_by(Visitor.id, Visitor.full_name)
        .having(func.count(func.distinct(Visit.location_id)) >= 2)
        .all()
    )
    for visitor_id, name, loc_cnt in multi:
        fp = f"MULTI_LOCATION:{visitor_id}:{loc_cnt}"
        loc_names = [
            r[0] for r in db.query(Location.name)
            .join(Visit, Visit.location_id == Location.id)
            .filter(Visit.visitor_id == visitor_id, Visit.location_id.in_(location_ids))
            .distinct()
            .all()
        ]
        evidence = {"bullets": [f"Visits across {loc_cnt} locations: {', '.join(loc_names[:5])}"], "confidence": "LIMITED_EVIDENCE"}
        if _upsert_insight(
            db, fp, "MULTI_LOCATION_VISITOR", "INFORMATION",
            "Multi-location visitor",
            f"{name} has visits across {loc_cnt} authorized locations in the last 30 days.",
            evidence, None, None, visitor_id,
        ):
            created += 1

    # Duplicate registration pattern (from security screening)
    screenings = (
        db.query(SecurityScreening)
        .options(joinedload(SecurityScreening.visit).joinedload(Visit.visitor))
        .filter(
            SecurityScreening.location_id.in_(location_ids),
            SecurityScreening.duplicate_signal_level.isnot(None),
            SecurityScreening.screened_at >= now - timedelta(days=7),
        )
        .limit(50)
        .all()
    )
    for sc in screenings:
        dv = sc.visit
        if not dv or not sc.duplicate_signal_level:
            continue
        fp = f"DUPLICATE_PATTERN:{dv.id}:{sc.duplicate_signal_level}"
        evidence = {"bullets": [f"Duplicate signal: {sc.duplicate_signal_level}", f"Visit {dv.registration_reference}"], "confidence": "CLEAR_EVIDENCE"}
        if _upsert_insight(
            db, fp, "DUPLICATE_REGISTRATION_PATTERN", "INFORMATION",
            "Duplicate registration pattern",
            f"Visit {dv.registration_reference} flagged with duplicate registration signal.",
            evidence, dv.location_id, dv.id, dv.visitor_id,
        ):
            created += 1

    db.commit()
    return created


def refresh_insights(db: Session, ctx: AuthContext, location_id: Optional[int] = None) -> int:
    if not role_has_permission(ctx.role, Permission.AI_INSIGHTS_READ):
        raise IntelligenceError("forbidden", "Permission denied.", 403)
    allowed = get_allowed_location_ids(ctx, db, location_id)
    if allowed is None:
        location_ids = [location_id] if location_id else [r[0] for r in db.query(Location.id).filter(Location.is_active.is_(True)).all()]
    elif not allowed:
        raise IntelligenceError("forbidden", "No accessible locations.", 403)
    else:
        location_ids = allowed
    return generate_insights_for_locations(db, location_ids)


def list_insights(
    db: Session,
    ctx: AuthContext,
    location_id: Optional[int] = None,
    priority: Optional[str] = None,
    insight_type: Optional[str] = None,
    status: Optional[str] = "ACTIVE",
    limit: int = 100,
) -> List[Dict[str, Any]]:
    if not role_has_permission(ctx.role, Permission.AI_INSIGHTS_READ):
        raise IntelligenceError("forbidden", "Permission denied.", 403)
    allowed = get_allowed_location_ids(ctx, db, location_id)
    if allowed is None:
        loc_filter = [location_id] if location_id else None
    elif not allowed:
        return []
    else:
        loc_filter = allowed if location_id is None else [location_id]

    q = db.query(AIInsight).order_by(
        AIInsight.priority.desc(),
        AIInsight.generated_at.desc(),
    )
    if status:
        q = q.filter(AIInsight.status == status)
    if priority:
        q = q.filter(AIInsight.priority == priority)
    if insight_type:
        q = q.filter(AIInsight.insight_type == insight_type)
    if loc_filter is not None:
        q = q.filter(
            (AIInsight.location_id.in_(loc_filter)) | (AIInsight.location_id.is_(None))
        )
    rows = q.limit(min(limit, 200)).all()
    out = []
    for r in rows:
        loc_name = None
        if r.location_id:
            loc = db.query(Location).filter(Location.id == r.location_id).first()
            loc_name = loc.name if loc else None
        evidence = json.loads(r.evidence_json) if r.evidence_json else {}
        out.append({
            "id": r.id,
            "insight_type": r.insight_type,
            "location_id": r.location_id,
            "location_name": loc_name,
            "visit_id": r.visit_id,
            "visitor_id": r.visitor_id,
            "status": r.status,
            "priority": r.priority,
            "title": r.title,
            "summary": r.summary,
            "evidence": evidence,
            "generated_at": r.generated_at.isoformat() if r.generated_at else None,
            "deep_link": _deep_link_for(r),
        })
    return out


def _deep_link_for(insight: AIInsight) -> Optional[str]:
    mapping = {
        "OVERSTAY_ATTENTION": "/onsite-now",
        "APPROVAL_DELAY": "/approvals",
        "SECURITY_REVIEW_AGING": "/security-review",
        "COMPLIANCE_ATTENTION": "/vendors-contractors",
        "REPEATED_REJECTIONS": "/approvals",
        "DUPLICATE_REGISTRATION_PATTERN": "/security-review",
    }
    return mapping.get(insight.insight_type, "/vms-copilot")


def dismiss_insight(db: Session, ctx: AuthContext, insight_id: int) -> Dict[str, Any]:
    if not role_has_permission(ctx.role, Permission.AI_INSIGHTS_DISMISS):
        raise IntelligenceError("forbidden", "Permission denied.", 403)
    insight = db.query(AIInsight).filter(AIInsight.id == insight_id).first()
    if not insight:
        raise IntelligenceError("not_found", "Insight not found.", 404)
    if insight.location_id:
        allowed = get_allowed_location_ids(ctx, db, insight.location_id)
        if allowed is not None and insight.location_id not in allowed:
            raise IntelligenceError("forbidden", "Permission denied.", 403)
    insight.status = "DISMISSED"
    insight.dismissed_at = datetime.now(timezone.utc)
    insight.dismissed_by_user_id = ctx.user_id
    AuditService(db).record(
        action="AI_INSIGHT_DISMISSED",
        entity_type="ai_insight",
        entity_id=str(insight_id),
        actor_id=ctx.user_id,
        actor_email=ctx.email,
        location_id=insight.location_id,
    )
    db.commit()
    return {"id": insight_id, "status": "DISMISSED"}
