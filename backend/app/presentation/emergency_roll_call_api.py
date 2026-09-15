from __future__ import annotations

from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.application.auth_service import AuthContext
from app.application.emergency_roll_call_service import (
    EmergencyRollCallError,
    close_emergency,
    count_onsite_visitors,
    get_emergency,
    get_roll_call_entry_detail,
    list_active_emergencies,
    list_emergency_history,
    list_emergency_overview,
    list_roll_call,
    start_emergency,
    update_roll_call_status,
)
from app.core.errors import APIError
from app.infrastructure.database import get_db
from app.presentation.dependencies import require_auth
from app.presentation.schemas import (
    CloseEmergencyRequest,
    EmergencyEventItem,
    EmergencyHistoryListResponse,
    EmergencyOverviewItem,
    EmergencyRollCallEntryItem,
    StartEmergencyRequest,
    UpdateRollCallStatusRequest,
)

router = APIRouter(tags=["emergency-roll-call"])


def _err(exc: EmergencyRollCallError) -> None:
    raise APIError(exc.status_code, exc.code, exc.message)


@router.get("/emergencies/active", response_model=List[EmergencyEventItem])
def active_emergencies(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
    location_id: Annotated[Optional[int], Query()] = None,
) -> List[EmergencyEventItem]:
    try:
        items = list_active_emergencies(db, user, location_id=location_id)
    except EmergencyRollCallError as exc:
        _err(exc)
    return [EmergencyEventItem(**i) for i in items]


@router.get("/emergencies/overview", response_model=List[EmergencyOverviewItem])
def emergency_overview(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
) -> List[EmergencyOverviewItem]:
    try:
        items = list_emergency_overview(db, user)
    except EmergencyRollCallError as exc:
        _err(exc)
    return [EmergencyOverviewItem(**i) for i in items]


@router.get("/emergencies/history", response_model=EmergencyHistoryListResponse)
def emergency_history(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
    location_id: Annotated[Optional[int], Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> EmergencyHistoryListResponse:
    try:
        items, total = list_emergency_history(db, user, location_id=location_id, limit=limit, offset=offset)
    except EmergencyRollCallError as exc:
        _err(exc)
    return EmergencyHistoryListResponse(
        items=[EmergencyEventItem(**i) for i in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/emergencies/onsite-count")
def emergency_onsite_count(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
    location_id: Annotated[int, Query(gt=0)],
) -> dict:
    try:
        count = count_onsite_visitors(db, user, location_id)
    except EmergencyRollCallError as exc:
        _err(exc)
    return {"location_id": location_id, "onsite_count": count}


@router.post("/emergencies", response_model=EmergencyEventItem)
def create_emergency(
    body: StartEmergencyRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
) -> EmergencyEventItem:
    try:
        detail = start_emergency(db, user, body.location_id, body.reason, notes=body.notes)
    except EmergencyRollCallError as exc:
        _err(exc)
    return EmergencyEventItem(**detail)


@router.get("/emergencies/{emergency_id}", response_model=EmergencyEventItem)
def get_emergency_detail(
    emergency_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
) -> EmergencyEventItem:
    try:
        detail = get_emergency(db, user, emergency_id)
    except EmergencyRollCallError as exc:
        _err(exc)
    return EmergencyEventItem(**detail)


@router.get("/emergencies/{emergency_id}/roll-call", response_model=List[EmergencyRollCallEntryItem])
def roll_call_list(
    emergency_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
    search: Annotated[Optional[str], Query(max_length=100)] = None,
) -> List[EmergencyRollCallEntryItem]:
    try:
        items = list_roll_call(db, user, emergency_id, search=search)
    except EmergencyRollCallError as exc:
        _err(exc)
    return [EmergencyRollCallEntryItem(**i) for i in items]


@router.get("/emergencies/{emergency_id}/entries/{entry_id}", response_model=EmergencyRollCallEntryItem)
def roll_call_entry_detail(
    emergency_id: int,
    entry_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
) -> EmergencyRollCallEntryItem:
    try:
        detail = get_roll_call_entry_detail(db, user, emergency_id, entry_id)
    except EmergencyRollCallError as exc:
        _err(exc)
    return EmergencyRollCallEntryItem(**detail)


@router.post("/emergencies/{emergency_id}/entries/{entry_id}/status", response_model=EmergencyRollCallEntryItem)
def roll_call_status_update(
    emergency_id: int,
    entry_id: int,
    body: UpdateRollCallStatusRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
) -> EmergencyRollCallEntryItem:
    try:
        detail = update_roll_call_status(
            db, user, emergency_id, entry_id,
            body.status,
            comment=body.comment,
            expected_version=body.expected_version,
        )
    except EmergencyRollCallError as exc:
        _err(exc)
    return EmergencyRollCallEntryItem(**detail)


@router.post("/emergencies/{emergency_id}/close", response_model=EmergencyEventItem)
def close_emergency_endpoint(
    emergency_id: int,
    body: CloseEmergencyRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
) -> EmergencyEventItem:
    try:
        detail = close_emergency(
            db, user, emergency_id,
            closure_comment=body.closure_comment,
            confirm_unresolved=body.confirm_unresolved,
        )
    except EmergencyRollCallError as exc:
        _err(exc)
    return EmergencyEventItem(**detail)
