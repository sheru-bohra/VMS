"""Management analytics derived from operational source data."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session, joinedload

from app.application.auth_service import AuthContext
from app.application.site_scope_service import get_allowed_location_ids
from app.application.timezone_service import get_location_day_bounds, resolve_timezone
from app.core.config import settings
from app.domain.enums import (
    AdminRole,
    ComplianceStatus,
    Permission,
    SecurityClearanceStatus,
    VisitSource,
    VisitStatus,
    role_has_permission,
)
from app.application.operations_service import _build_visit_dict
from app.domain.models import (
    EmergencyEvent,
    Location,
    Visit,
    VisitApproval,
    Visitor,
    VisitorType,
)

DASHBOARD_KPI_KEYS = frozenset({
    "expected_today",
    "awaiting_approval",
    "checked_in_today",
    "onsite_now",
    "checked_out_today",
    "overstayed",
    "vendor_contractor_onsite",
})

_EXPECTED_TODAY_STATUSES = frozenset({
    VisitStatus.APPROVED.value,
    VisitStatus.ARRIVED.value,
    VisitStatus.CHECKED_IN.value,
    VisitStatus.ONSITE.value,
    VisitStatus.CHECKED_OUT.value,
})


class AnalyticsError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


OPERATIONAL_STAFF_ROLES = frozenset({
    AdminRole.GLOBAL_ADMIN,
    AdminRole.HEAD_ADMIN,
    AdminRole.SITE_ADMIN,
    AdminRole.SECURITY,
})


def _can_view_operational_dashboard(ctx: AuthContext) -> bool:
    return ctx.role in OPERATIONAL_STAFF_ROLES


def _require_dashboard(ctx: AuthContext) -> None:
    if role_has_permission(ctx.role, Permission.ANALYTICS_DASHBOARD_VIEW):
        return
    if _can_view_operational_dashboard(ctx):
        return
    raise AnalyticsError("forbidden", "Permission denied.", 403)


def _resolve_location_ids(db: Session, ctx: AuthContext, location_id: Optional[int]) -> List[int]:
    allowed = get_allowed_location_ids(ctx, db, location_id)
    if allowed is None:
        if location_id is not None:
            return [location_id]
        return [r[0] for r in db.query(Location.id).filter(Location.is_active.is_(True)).all()]
    if not allowed:
        raise AnalyticsError("forbidden", "No accessible locations.", 403)
    return allowed


def _parse_period(
    period: Optional[str],
    from_dt: Optional[datetime],
    to_dt: Optional[datetime],
    tz_name: Optional[str],
) -> Tuple[datetime, datetime, str]:
    tz = resolve_timezone(tz_name)
    now = datetime.now(timezone.utc)
    local_now = now.astimezone(tz)
    p = (period or "today").lower().replace("-", "_")

    if p == "custom" and from_dt and to_dt:
        start = from_dt if from_dt.tzinfo else from_dt.replace(tzinfo=timezone.utc)
        end = to_dt if to_dt.tzinfo else to_dt.replace(tzinfo=timezone.utc)
        if end <= start:
            raise AnalyticsError("invalid_range", "End date must be after start date.")
        days = (end - start).days
        if days > settings.analytics_max_range_days:
            raise AnalyticsError("range_too_large", f"Maximum range is {settings.analytics_max_range_days} days.")
        return start, end, "custom"

    if p == "last_7_days":
        end = now
        start = now - timedelta(days=7)
        return start, end, p
    if p == "last_30_days":
        end = now
        start = now - timedelta(days=30)
        return start, end, p
    if p == "this_month":
        start_local = datetime(local_now.year, local_now.month, 1, tzinfo=tz)
        if local_now.month == 12:
            end_local = datetime(local_now.year + 1, 1, 1, tzinfo=tz)
        else:
            end_local = datetime(local_now.year, local_now.month + 1, 1, tzinfo=tz)
        return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc), p

    start, end = get_location_day_bounds(tz_name)
    return start, end, "today"


def _scoped_visit_query(
    db: Session,
    location_ids: List[int],
    visitor_type_id: Optional[int] = None,
    source: Optional[str] = None,
):
    query = db.query(Visit).filter(Visit.location_id.in_(location_ids))
    if visitor_type_id:
        query = query.join(Visitor).filter(Visitor.visitor_type_id == visitor_type_id)
    if source:
        query = query.filter(Visit.source == source)
    return query


def _count_checked_in_on_local_days(db: Session, location_ids: List[int], reference: Optional[datetime] = None) -> int:
    total = 0
    for loc_id in location_ids:
        loc = db.query(Location).filter(Location.id == loc_id).first()
        start, end = get_location_day_bounds(loc.timezone if loc else None, reference)
        total += (
            db.query(Visit)
            .filter(
                Visit.location_id == loc_id,
                Visit.checked_in_at.isnot(None),
                Visit.checked_in_at >= start,
                Visit.checked_in_at < end,
            )
            .count()
        )
    return total


def _count_checked_out_on_local_days(db: Session, location_ids: List[int], reference: Optional[datetime] = None) -> int:
    total = 0
    for loc_id in location_ids:
        loc = db.query(Location).filter(Location.id == loc_id).first()
        start, end = get_location_day_bounds(loc.timezone if loc else None, reference)
        total += (
            db.query(Visit)
            .filter(
                Visit.location_id == loc_id,
                Visit.checked_out_at.isnot(None),
                Visit.checked_out_at >= start,
                Visit.checked_out_at < end,
            )
            .count()
        )
    return total


def _count_expected_today(db: Session, location_ids: List[int]) -> int:
    total = 0
    for loc_id in location_ids:
        loc = db.query(Location).filter(Location.id == loc_id).first()
        if not loc:
            continue
        start, end = get_location_day_bounds(loc.timezone)
        q = (
            db.query(Visit)
            .filter(
                Visit.location_id == loc_id,
                Visit.source.in_([VisitSource.SELF_REGISTRATION.value, VisitSource.ADVANCE_REGISTRATION.value]),
                Visit.status.in_([
                    VisitStatus.APPROVED.value,
                    VisitStatus.ARRIVED.value,
                    VisitStatus.CHECKED_IN.value,
                    VisitStatus.ONSITE.value,
                    VisitStatus.CHECKED_OUT.value,
                ]),
            )
        )
        q = q.filter(
            or_(
                and_(Visit.source == VisitSource.SELF_REGISTRATION.value, Visit.created_at >= start, Visit.created_at < end),
                and_(Visit.scheduled_start.isnot(None), Visit.scheduled_start >= start, Visit.scheduled_start < end),
            )
        )
        total += q.count()
    return total


def _count_overstayed(db: Session, location_ids: List[int]) -> int:
    now = datetime.now(timezone.utc)
    visits = (
        db.query(Visit)
        .filter(Visit.location_id.in_(location_ids), Visit.status == VisitStatus.ONSITE.value)
        .all()
    )
    count = 0
    for v in visits:
        if v.checked_in_at and v.expected_duration_minutes:
            checked = v.checked_in_at
            if checked.tzinfo is None:
                checked = checked.replace(tzinfo=timezone.utc)
            if now > checked + timedelta(minutes=v.expected_duration_minutes):
                count += 1
    return count


def _count_vendor_contractor_onsite(db: Session, location_ids: List[int]) -> int:
    return (
        db.query(Visit)
        .join(Visitor)
        .join(VisitorType)
        .filter(
            Visit.location_id.in_(location_ids),
            Visit.status == VisitStatus.ONSITE.value,
            VisitorType.requires_vendor_compliance.is_(True),
        )
        .count()
    )


def _build_hourly_trend(
    db: Session,
    location_ids: List[int],
    tz_name: Optional[str],
    range_start: datetime,
    range_end: datetime,
) -> List[Dict[str, Any]]:
    """Hourly buckets for the selected local calendar day."""
    tz = resolve_timezone(tz_name)
    trend: List[Dict[str, Any]] = []
    for h in range(24):
        hour_start = range_start + timedelta(hours=h)
        hour_end = hour_start + timedelta(hours=1)
        if hour_start >= range_end:
            break
        label = hour_start.astimezone(tz).strftime("%H:00")
        checked_in = sum(
            db.query(Visit)
            .filter(
                Visit.location_id == lid,
                Visit.checked_in_at.isnot(None),
                Visit.checked_in_at >= hour_start,
                Visit.checked_in_at < hour_end,
            )
            .count()
            for lid in location_ids
        )
        checked_out = sum(
            db.query(Visit)
            .filter(
                Visit.location_id == lid,
                Visit.checked_out_at.isnot(None),
                Visit.checked_out_at >= hour_start,
                Visit.checked_out_at < hour_end,
            )
            .count()
            for lid in location_ids
        )
        trend.append({
            "date": hour_start.isoformat(),
            "label": label,
            "granularity": "hour",
            "expected": 0,
            "checked_in": checked_in,
            "checked_out": checked_out,
        })
    return trend


def _build_daily_trend(
    db: Session,
    location_ids: List[int],
    range_start: datetime,
    range_end: datetime,
) -> List[Dict[str, Any]]:
    trend: List[Dict[str, Any]] = []
    days = max(1, min((range_end - range_start).days, 90))
    for i in range(days):
        day_start = range_start + timedelta(days=i)
        day_end = day_start + timedelta(days=1)
        if day_end > range_end:
            break
        date_label = day_start.strftime("%Y-%m-%d")
        display_label = day_start.strftime("%m-%d")
        expected = 0
        for loc_id in location_ids:
            loc = db.query(Location).filter(Location.id == loc_id).first()
            ls, le = get_location_day_bounds(loc.timezone if loc else None, day_start + timedelta(hours=12))
            expected += (
                db.query(Visit)
                .filter(
                    Visit.location_id == loc_id,
                    Visit.source.in_([VisitSource.SELF_REGISTRATION.value, VisitSource.ADVANCE_REGISTRATION.value]),
                    or_(
                        and_(Visit.source == VisitSource.SELF_REGISTRATION.value, Visit.created_at >= ls, Visit.created_at < le),
                        and_(Visit.scheduled_start.isnot(None), Visit.scheduled_start >= ls, Visit.scheduled_start < le),
                    ),
                )
                .count()
            )
        checked_in = sum(
            db.query(Visit)
            .filter(
                Visit.location_id == lid,
                Visit.checked_in_at.isnot(None),
                Visit.checked_in_at >= day_start,
                Visit.checked_in_at < day_end,
            )
            .count()
            for lid in location_ids
        )
        checked_out = sum(
            db.query(Visit)
            .filter(
                Visit.location_id == lid,
                Visit.checked_out_at.isnot(None),
                Visit.checked_out_at >= day_start,
                Visit.checked_out_at < day_end,
            )
            .count()
            for lid in location_ids
        )
        trend.append({
            "date": date_label,
            "label": display_label,
            "granularity": "day",
            "expected": expected,
            "checked_in": checked_in,
            "checked_out": checked_out,
        })
    return trend


def get_dashboard(
    db: Session,
    ctx: AuthContext,
    period: Optional[str] = None,
    from_dt: Optional[datetime] = None,
    to_dt: Optional[datetime] = None,
    location_id: Optional[int] = None,
    visitor_type_id: Optional[int] = None,
    source: Optional[str] = None,
) -> Dict[str, Any]:
    _require_dashboard(ctx)
    location_ids = _resolve_location_ids(db, ctx, location_id)
    tz_name = None
    if location_id:
        loc = db.query(Location).filter(Location.id == location_id).first()
        tz_name = loc.timezone if loc else None

    range_start, range_end, period_key = _parse_period(period, from_dt, to_dt, tz_name)

    kpis = {
        "expected_today": _count_expected_today(db, location_ids),
        "awaiting_approval": _scoped_visit_query(db, location_ids, visitor_type_id, source)
        .filter(Visit.status == VisitStatus.PENDING_APPROVAL.value).count(),
        "checked_in_today": _count_checked_in_on_local_days(db, location_ids),
        "onsite_now": _scoped_visit_query(db, location_ids, visitor_type_id, source)
        .filter(Visit.status == VisitStatus.ONSITE.value).count(),
        "checked_out_today": _count_checked_out_on_local_days(db, location_ids),
        "overstayed": _count_overstayed(db, location_ids),
        "vendor_contractor_onsite": _count_vendor_contractor_onsite(db, location_ids),
    }

    trend: List[Dict[str, Any]] = []
    if role_has_permission(ctx.role, Permission.ANALYTICS_TRENDS_VIEW) or _can_view_operational_dashboard(ctx):
        if period_key == "today":
            trend = _build_hourly_trend(db, location_ids, tz_name, range_start, range_end)
        else:
            trend = _build_daily_trend(db, location_ids, range_start, range_end)

    visitor_types: List[Dict[str, Any]] = []
    if role_has_permission(ctx.role, Permission.ANALYTICS_TRENDS_VIEW) or _can_view_operational_dashboard(ctx):
        rows = (
            db.query(VisitorType.name, func.count(Visit.id))
            .join(Visitor, Visitor.visitor_type_id == VisitorType.id)
            .join(Visit, Visit.visitor_id == Visitor.id)
            .filter(
                Visit.location_id.in_(location_ids),
                Visit.created_at >= range_start,
                Visit.created_at < range_end,
            )
            .group_by(VisitorType.name)
            .all()
        )
        visitor_types = [{"name": name, "count": cnt} for name, cnt in rows]

    locations_compare: List[Dict[str, Any]] = []
    if role_has_permission(ctx.role, Permission.ANALYTICS_LOCATIONS_COMPARE) or _can_view_operational_dashboard(ctx):
        for loc_id in location_ids:
            loc = db.query(Location).filter(Location.id == loc_id).first()
            if not loc or loc.is_development_seed:
                continue
            ls, le = get_location_day_bounds(loc.timezone if range_end - range_start <= timedelta(days=1) else None)
            use_start, use_end = (ls, le) if period_key == "today" else (range_start, range_end)
            visitors = (
                db.query(Visit)
                .filter(Visit.location_id == loc_id, Visit.created_at >= use_start, Visit.created_at < use_end)
                .count()
            )
            check_ins = (
                db.query(Visit)
                .filter(
                    Visit.location_id == loc_id,
                    Visit.checked_in_at.isnot(None),
                    Visit.checked_in_at >= use_start,
                    Visit.checked_in_at < use_end,
                )
                .count()
            )
            onsite = db.query(Visit).filter(Visit.location_id == loc_id, Visit.status == VisitStatus.ONSITE.value).count()
            rejected = (
                db.query(Visit)
                .filter(Visit.location_id == loc_id, Visit.status == VisitStatus.REJECTED.value, Visit.created_at >= use_start, Visit.created_at < use_end)
                .count()
            )
            locations_compare.append({
                "location_id": loc.id,
                "location_name": loc.name,
                "visitors": visitors,
                "check_ins": check_ins,
                "onsite": onsite,
                "rejected": rejected,
            })

    peak_arrivals: List[Dict[str, Any]] = []
    hour_rows = (
        db.query(func.strftime("%H", Visit.checked_in_at), func.count(Visit.id))
        .filter(
            Visit.location_id.in_(location_ids),
            Visit.checked_in_at.isnot(None),
            Visit.checked_in_at >= range_start,
            Visit.checked_in_at < range_end,
        )
        .group_by(func.strftime("%H", Visit.checked_in_at))
        .all()
    )
    for hour_str, cnt in hour_rows:
        if hour_str is None:
            continue
        h = int(hour_str)
        peak_arrivals.append({"hour": h, "label": f"{h:02d}:00–{(h + 1) % 24:02d}:00", "count": cnt})

    approval_durations: List[float] = []
    approvals = (
        db.query(VisitApproval)
        .join(Visit)
        .filter(
            Visit.location_id.in_(location_ids),
            VisitApproval.decision == "APPROVED",
            VisitApproval.created_at >= range_start,
            VisitApproval.created_at < range_end,
        )
        .all()
    )
    for ap in approvals:
        visit = ap.visit
        if visit and visit.created_at and ap.created_at:
            delta = (ap.created_at - visit.created_at).total_seconds()
            if delta >= 0:
                approval_durations.append(delta)
    approval_metrics = {
        "average_minutes": round(sum(approval_durations) / len(approval_durations) / 60, 1) if approval_durations else 0,
        "median_minutes": round(sorted(approval_durations)[len(approval_durations) // 2] / 60, 1) if approval_durations else 0,
        "sample_size": len(approval_durations),
    }

    durations: List[float] = []
    completed = (
        db.query(Visit)
        .filter(
            Visit.location_id.in_(location_ids),
            Visit.checked_in_at.isnot(None),
            Visit.checked_out_at.isnot(None),
            Visit.checked_out_at >= range_start,
            Visit.checked_out_at < range_end,
        )
        .all()
    )
    for v in completed:
        if v.checked_in_at and v.checked_out_at:
            durations.append((v.checked_out_at - v.checked_in_at).total_seconds())
    visit_duration = {
        "average_minutes": round(sum(durations) / len(durations) / 60, 1) if durations else 0,
        "sample_size": len(durations),
    }

    security_summary = {
        "review": _scoped_visit_query(db, location_ids).filter(Visit.security_clearance_status == SecurityClearanceStatus.REVIEW.value).count(),
        "blocked": _scoped_visit_query(db, location_ids).filter(Visit.security_clearance_status == SecurityClearanceStatus.BLOCKED.value).count(),
    }
    compliance_summary = {
        "review_required": _scoped_visit_query(db, location_ids).filter(Visit.compliance_status == ComplianceStatus.REVIEW_REQUIRED.value).count(),
        "non_compliant": _scoped_visit_query(db, location_ids).filter(Visit.compliance_status == ComplianceStatus.NON_COMPLIANT.value).count(),
        "expiring": _scoped_visit_query(db, location_ids).filter(Visit.compliance_status == ComplianceStatus.EXPIRING.value).count(),
    }

    active_emergencies = []
    if role_has_permission(ctx.role, Permission.EMERGENCY_READ):
        events = (
            db.query(EmergencyEvent)
            .filter(EmergencyEvent.location_id.in_(location_ids), EmergencyEvent.status == "ACTIVE")
            .all()
        )
        for e in events:
            loc = db.query(Location).filter(Location.id == e.location_id).first()
            active_emergencies.append({
                "id": e.id,
                "location_id": e.location_id,
                "location_name": loc.name if loc else None,
                "started_at": e.started_at.isoformat() if e.started_at else None,
            })

    loc_label = "All authorized locations"
    if location_id:
        loc = db.query(Location).filter(Location.id == location_id).first()
        loc_label = loc.name if loc else str(location_id)

    return {
        "range": {
            "period": period_key,
            "from": range_start.isoformat(),
            "to": range_end.isoformat(),
            "location_id": location_id,
            "location_label": loc_label,
        },
        "kpis": kpis,
        "visitor_trend": trend,
        "visitor_types": visitor_types,
        "locations": locations_compare,
        "peak_arrivals": sorted(peak_arrivals, key=lambda x: x["hour"]),
        "approval_metrics": approval_metrics,
        "visit_duration": visit_duration,
        "security_summary": security_summary,
        "compliance_summary": compliance_summary,
        "active_emergencies": active_emergencies,
    }


def _visit_load_options():
    return [
        joinedload(Visit.visitor).joinedload(Visitor.visitor_type),
        joinedload(Visit.location),
        joinedload(Visit.approvals),
    ]


def _sort_visits_desc(visits: List[Visit], attr: str) -> List[Visit]:
    def sort_key(v: Visit) -> datetime:
        value = getattr(v, attr, None)
        if value is None:
            return datetime.min.replace(tzinfo=timezone.utc)
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    return sorted(visits, key=sort_key, reverse=True)


def _collect_expected_today_visits(db: Session, location_ids: List[int]) -> List[Visit]:
    visits: List[Visit] = []
    for loc_id in location_ids:
        loc = db.query(Location).filter(Location.id == loc_id).first()
        if not loc:
            continue
        start, end = get_location_day_bounds(loc.timezone)
        rows = (
            db.query(Visit)
            .options(*_visit_load_options())
            .filter(
                Visit.location_id == loc_id,
                Visit.source.in_([VisitSource.SELF_REGISTRATION.value, VisitSource.ADVANCE_REGISTRATION.value]),
                Visit.status.in_(list(_EXPECTED_TODAY_STATUSES)),
            )
            .filter(
                or_(
                    and_(Visit.source == VisitSource.SELF_REGISTRATION.value, Visit.created_at >= start, Visit.created_at < end),
                    and_(Visit.scheduled_start.isnot(None), Visit.scheduled_start >= start, Visit.scheduled_start < end),
                )
            )
            .all()
        )
        visits.extend(rows)
    return visits


def _collect_checked_in_today_visits(db: Session, location_ids: List[int]) -> List[Visit]:
    visits: List[Visit] = []
    for loc_id in location_ids:
        loc = db.query(Location).filter(Location.id == loc_id).first()
        start, end = get_location_day_bounds(loc.timezone if loc else None)
        rows = (
            db.query(Visit)
            .options(*_visit_load_options())
            .filter(
                Visit.location_id == loc_id,
                Visit.checked_in_at.isnot(None),
                Visit.checked_in_at >= start,
                Visit.checked_in_at < end,
            )
            .all()
        )
        visits.extend(rows)
    return visits


def _collect_checked_out_today_visits(db: Session, location_ids: List[int]) -> List[Visit]:
    visits: List[Visit] = []
    for loc_id in location_ids:
        loc = db.query(Location).filter(Location.id == loc_id).first()
        start, end = get_location_day_bounds(loc.timezone if loc else None)
        rows = (
            db.query(Visit)
            .options(*_visit_load_options())
            .filter(
                Visit.location_id == loc_id,
                Visit.checked_out_at.isnot(None),
                Visit.checked_out_at >= start,
                Visit.checked_out_at < end,
            )
            .all()
        )
        visits.extend(rows)
    return visits


def _collect_overstayed_visits(db: Session, location_ids: List[int]) -> List[Visit]:
    now = datetime.now(timezone.utc)
    rows = (
        db.query(Visit)
        .options(*_visit_load_options())
        .filter(Visit.location_id.in_(location_ids), Visit.status == VisitStatus.ONSITE.value)
        .all()
    )
    overstayed: List[Visit] = []
    for visit in rows:
        if not visit.checked_in_at or not visit.expected_duration_minutes:
            continue
        checked = visit.checked_in_at
        if checked.tzinfo is None:
            checked = checked.replace(tzinfo=timezone.utc)
        if now > checked + timedelta(minutes=visit.expected_duration_minutes):
            overstayed.append(visit)
    return overstayed


def _collect_vendor_contractor_onsite_visits(db: Session, location_ids: List[int]) -> List[Visit]:
    return (
        db.query(Visit)
        .options(*_visit_load_options())
        .join(Visitor)
        .join(VisitorType)
        .filter(
            Visit.location_id.in_(location_ids),
            Visit.status == VisitStatus.ONSITE.value,
            VisitorType.requires_vendor_compliance.is_(True),
        )
        .all()
    )


def list_dashboard_kpi(
    db: Session,
    ctx: AuthContext,
    kpi_key: str,
    location_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[List[Dict[str, Any]], int]:
    _require_dashboard(ctx)
    key = (kpi_key or "").lower().replace("-", "_")
    if key not in DASHBOARD_KPI_KEYS:
        raise AnalyticsError("invalid_kpi", f"Unknown dashboard KPI: {kpi_key}", 400)

    location_ids = _resolve_location_ids(db, ctx, location_id)
    limit = max(1, min(limit, 100))
    offset = max(0, offset)

    if key == "expected_today":
        visits = _sort_visits_desc(_collect_expected_today_visits(db, location_ids), "scheduled_start")
    elif key == "awaiting_approval":
        visits = _sort_visits_desc(
            (
                db.query(Visit)
                .options(*_visit_load_options())
                .filter(
                    Visit.location_id.in_(location_ids),
                    Visit.status == VisitStatus.PENDING_APPROVAL.value,
                )
                .all()
            ),
            "created_at",
        )
    elif key == "checked_in_today":
        visits = _sort_visits_desc(_collect_checked_in_today_visits(db, location_ids), "checked_in_at")
    elif key == "onsite_now":
        visits = _sort_visits_desc(
            (
                db.query(Visit)
                .options(*_visit_load_options())
                .filter(Visit.location_id.in_(location_ids), Visit.status == VisitStatus.ONSITE.value)
                .all()
            ),
            "checked_in_at",
        )
    elif key == "checked_out_today":
        visits = _sort_visits_desc(_collect_checked_out_today_visits(db, location_ids), "checked_out_at")
    elif key == "overstayed":
        visits = _sort_visits_desc(_collect_overstayed_visits(db, location_ids), "checked_in_at")
    else:
        visits = _sort_visits_desc(_collect_vendor_contractor_onsite_visits(db, location_ids), "checked_in_at")

    total = len(visits)
    page = visits[offset: offset + limit]
    return [_build_visit_dict(v) for v in page], total
