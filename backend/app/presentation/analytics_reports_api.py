from __future__ import annotations

from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.application.analytics_service import AnalyticsError, get_dashboard, list_dashboard_kpi
from app.application.auth_service import AuthContext
from app.application.report_service import ReportError, export_visits_csv, export_visits_xlsx, list_visit_reports
from app.core.errors import APIError
from app.infrastructure.database import get_db
from app.presentation.dependencies import require_auth
from app.presentation.schemas import ExpectedTodayListResponse, OperationalVisitItem

router_analytics = APIRouter(tags=["analytics"])
router_reports = APIRouter(tags=["reports"])


def _analytics_err(exc: AnalyticsError) -> None:
    raise APIError(exc.status_code, exc.code, exc.message)


def _report_err(exc: ReportError) -> None:
    raise APIError(exc.status_code, exc.code, exc.message)


@router_analytics.get("/analytics/dashboard")
def dashboard(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
    period: Annotated[Optional[str], Query()] = "today",
    from_dt: Annotated[Optional[datetime], Query(alias="from")] = None,
    to_dt: Annotated[Optional[datetime], Query(alias="to")] = None,
    location_id: Annotated[Optional[int], Query()] = None,
    visitor_type_id: Annotated[Optional[int], Query()] = None,
    source: Annotated[Optional[str], Query()] = None,
):
    try:
        return get_dashboard(
            db, user, period=period, from_dt=from_dt, to_dt=to_dt,
            location_id=location_id, visitor_type_id=visitor_type_id, source=source,
        )
    except AnalyticsError as exc:
        _analytics_err(exc)


@router_analytics.get("/analytics/dashboard/kpi/{kpi_key}", response_model=ExpectedTodayListResponse)
def dashboard_kpi_drill_down(
    kpi_key: str,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
    location_id: Annotated[Optional[int], Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ExpectedTodayListResponse:
    try:
        items, total = list_dashboard_kpi(
            db, user, kpi_key, location_id=location_id, limit=limit, offset=offset,
        )
    except AnalyticsError as exc:
        _analytics_err(exc)
    return ExpectedTodayListResponse(
        items=[OperationalVisitItem(**item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router_reports.get("/reports/visits")
def reports_visits(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
    from_dt: Annotated[datetime, Query(alias="from")],
    to_dt: Annotated[datetime, Query(alias="to")],
    location_id: Annotated[Optional[int], Query()] = None,
    visitor_type_id: Annotated[Optional[int], Query()] = None,
    company: Annotated[Optional[str], Query(max_length=200)] = None,
    host_id: Annotated[Optional[int], Query()] = None,
    source: Annotated[Optional[str], Query()] = None,
    status: Annotated[Optional[str], Query()] = None,
    security_status: Annotated[Optional[str], Query()] = None,
    compliance_status: Annotated[Optional[str], Query()] = None,
    registration_reference: Annotated[Optional[str], Query(max_length=50)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    sort: Annotated[str, Query()] = "registered_at",
    sort_dir: Annotated[str, Query()] = "desc",
):
    try:
        items, total = list_visit_reports(
            db, user, from_dt, to_dt,
            location_id=location_id,
            visitor_type_id=visitor_type_id,
            company=company,
            host_id=host_id,
            source=source,
            status=status,
            security_status=security_status,
            compliance_status=compliance_status,
            registration_reference=registration_reference,
            page=page,
            page_size=page_size,
            sort=sort,
            sort_dir=sort_dir,
        )
    except ReportError as exc:
        _report_err(exc)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router_reports.get("/reports/visits/export.csv")
def export_csv(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
    from_dt: Annotated[datetime, Query(alias="from")],
    to_dt: Annotated[datetime, Query(alias="to")],
    location_id: Annotated[Optional[int], Query()] = None,
    visitor_type_id: Annotated[Optional[int], Query()] = None,
    company: Annotated[Optional[str], Query(max_length=200)] = None,
    host_id: Annotated[Optional[int], Query()] = None,
    source: Annotated[Optional[str], Query()] = None,
    status: Annotated[Optional[str], Query()] = None,
    security_status: Annotated[Optional[str], Query()] = None,
    compliance_status: Annotated[Optional[str], Query()] = None,
    registration_reference: Annotated[Optional[str], Query(max_length=50)] = None,
    location_label: Annotated[Optional[str], Query()] = None,
):
    filters = {
        "from_dt": from_dt, "to_dt": to_dt, "location_id": location_id,
        "visitor_type_id": visitor_type_id, "company": company, "host_id": host_id,
        "source": source, "status": status, "security_status": security_status,
        "compliance_status": compliance_status, "registration_reference": registration_reference,
        "location_label": location_label,
    }
    try:
        content, filename, _ = export_visits_csv(db, user, filters)
    except ReportError as exc:
        _report_err(exc)
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router_reports.get("/reports/visits/export.xlsx")
def export_xlsx(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
    from_dt: Annotated[datetime, Query(alias="from")],
    to_dt: Annotated[datetime, Query(alias="to")],
    location_id: Annotated[Optional[int], Query()] = None,
    visitor_type_id: Annotated[Optional[int], Query()] = None,
    company: Annotated[Optional[str], Query(max_length=200)] = None,
    host_id: Annotated[Optional[int], Query()] = None,
    source: Annotated[Optional[str], Query()] = None,
    status: Annotated[Optional[str], Query()] = None,
    security_status: Annotated[Optional[str], Query()] = None,
    compliance_status: Annotated[Optional[str], Query()] = None,
    registration_reference: Annotated[Optional[str], Query(max_length=50)] = None,
    location_label: Annotated[Optional[str], Query()] = None,
):
    filters = {
        "from_dt": from_dt, "to_dt": to_dt, "location_id": location_id,
        "visitor_type_id": visitor_type_id, "company": company, "host_id": host_id,
        "source": source, "status": status, "security_status": security_status,
        "compliance_status": compliance_status, "registration_reference": registration_reference,
        "location_label": location_label,
    }
    try:
        content, filename, _ = export_visits_xlsx(db, user, filters)
    except ReportError as exc:
        _report_err(exc)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
