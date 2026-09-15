from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.application.auth_service import AuthContext
from app.application.operations_service import (
    OperationsError,
    check_in_visit,
    check_out_visit,
    get_visit_detail,
    list_expected_today,
    list_onsite,
    list_visitor_visits,
    mark_arrived,
)
from app.core.errors import APIError
from app.infrastructure.database import get_db
from app.presentation.dependencies import require_auth
from app.presentation.schemas import (
    ExpectedTodayListResponse,
    OnsiteListResponse,
    OperationalVisitItem,
)

router = APIRouter(tags=["operations"])


def _handle_ops_error(exc: OperationsError) -> None:
    raise APIError(exc.status_code, exc.code, exc.message)


@router.get("/expected-today", response_model=ExpectedTodayListResponse)
def get_expected_today(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
    status: Annotated[Optional[str], Query()] = None,
    search: Annotated[Optional[str], Query(max_length=100)] = None,
    site: Annotated[Optional[int], Query()] = None,
    visitor_type: Annotated[Optional[str], Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ExpectedTodayListResponse:
    try:
        items, total = list_expected_today(
            db, user, status=status, search=search, site=site,
            visitor_type=visitor_type, limit=limit, offset=offset,
        )
    except OperationsError as exc:
        _handle_ops_error(exc)
    return ExpectedTodayListResponse(
        items=[OperationalVisitItem(**item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/onsite", response_model=OnsiteListResponse)
def get_onsite_visitors(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
    search: Annotated[Optional[str], Query(max_length=100)] = None,
    site: Annotated[Optional[int], Query()] = None,
    visitor_type: Annotated[Optional[str], Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> OnsiteListResponse:
    try:
        items, total, onsite_count = list_onsite(
            db, user, search=search, site=site,
            visitor_type=visitor_type, limit=limit, offset=offset,
        )
    except OperationsError as exc:
        _handle_ops_error(exc)
    return OnsiteListResponse(
        items=[OperationalVisitItem(**item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
        onsite_count=onsite_count,
    )


@router.get("/visitors", response_model=ExpectedTodayListResponse)
def get_visitor_visits(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
    status: Annotated[Optional[str], Query()] = None,
    search: Annotated[Optional[str], Query(max_length=100)] = None,
    site: Annotated[Optional[int], Query()] = None,
    visitor_type: Annotated[Optional[str], Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ExpectedTodayListResponse:
    try:
        items, total = list_visitor_visits(
            db, user, status=status, search=search, site=site,
            visitor_type=visitor_type, limit=limit, offset=offset,
        )
    except OperationsError as exc:
        _handle_ops_error(exc)
    return ExpectedTodayListResponse(
        items=[OperationalVisitItem(**item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/visits/{visit_id}", response_model=OperationalVisitItem)
def get_visit(
    visit_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
) -> OperationalVisitItem:
    try:
        detail = get_visit_detail(db, user, visit_id)
    except OperationsError as exc:
        _handle_ops_error(exc)
    return OperationalVisitItem(**detail)


@router.post("/visits/{visit_id}/arrive", response_model=OperationalVisitItem)
def arrive_visit(
    visit_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
) -> OperationalVisitItem:
    try:
        detail = mark_arrived(db, user, visit_id)
    except OperationsError as exc:
        _handle_ops_error(exc)
    return OperationalVisitItem(**detail)


@router.post("/visits/{visit_id}/check-in", response_model=OperationalVisitItem)
def visit_check_in(
    visit_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
) -> OperationalVisitItem:
    try:
        detail = check_in_visit(db, user, visit_id)
    except OperationsError as exc:
        _handle_ops_error(exc)
    return OperationalVisitItem(**detail)


@router.post("/visits/{visit_id}/check-out", response_model=OperationalVisitItem)
def visit_check_out(
    visit_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
) -> OperationalVisitItem:
    try:
        detail = check_out_visit(db, user, visit_id)
    except OperationsError as exc:
        _handle_ops_error(exc)
    return OperationalVisitItem(**detail)
