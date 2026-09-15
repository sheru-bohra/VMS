from __future__ import annotations

from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.application.auth_service import AuthContext
from app.application.watchlist_service import (
    WatchlistError,
    create_watchlist_entry,
    deactivate_watchlist_entry,
    get_watchlist_entry,
    list_watchlist,
    update_watchlist_entry,
)
from app.core.errors import APIError
from app.infrastructure.database import get_db
from app.presentation.dependencies import require_auth
from app.presentation.schemas import (
    CreateWatchlistRequest,
    UpdateWatchlistRequest,
    WatchlistItem,
    WatchlistListResponse,
)

router = APIRouter(tags=["watchlist"])


def _handle(exc: WatchlistError) -> None:
    raise APIError(exc.status_code, exc.code, exc.message)


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


@router.get("/watchlist", response_model=WatchlistListResponse)
def list_watchlist_entries(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
    search: Annotated[Optional[str], Query(max_length=100)] = None,
    scope: Annotated[Optional[str], Query()] = None,
    location_id: Annotated[Optional[int], Query()] = None,
    status: Annotated[Optional[str], Query()] = None,
    action_level: Annotated[Optional[str], Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> WatchlistListResponse:
    try:
        items, total = list_watchlist(
            db, user,
            search=search,
            scope=scope,
            location_id=location_id,
            status=status,
            action_level=action_level,
            limit=limit,
            offset=offset,
        )
    except WatchlistError as exc:
        _handle(exc)
    return WatchlistListResponse(
        items=[WatchlistItem(**item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/watchlist", response_model=WatchlistItem)
def create_entry(
    body: CreateWatchlistRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
) -> WatchlistItem:
    try:
        detail = create_watchlist_entry(
            db, user,
            scope_type=body.scope_type,
            full_name=body.full_name,
            reason_code=body.reason_code,
            action_level=body.action_level,
            valid_from=_parse_dt(body.valid_from),
            location_id=body.location_id,
            mobile=body.mobile,
            email=body.email,
            company=body.company,
            reason_text=body.reason_text,
            valid_until=_parse_dt(body.valid_until) if body.valid_until else None,
        )
    except WatchlistError as exc:
        _handle(exc)
    return WatchlistItem(**detail)


@router.get("/watchlist/{entry_id}", response_model=WatchlistItem)
def get_entry(
    entry_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
) -> WatchlistItem:
    try:
        detail = get_watchlist_entry(db, user, entry_id)
    except WatchlistError as exc:
        _handle(exc)
    return WatchlistItem(**detail)


@router.patch("/watchlist/{entry_id}", response_model=WatchlistItem)
def update_entry(
    entry_id: int,
    body: UpdateWatchlistRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
) -> WatchlistItem:
    try:
        detail = update_watchlist_entry(
            db, user, entry_id,
            action_level=body.action_level,
            reason_text=body.reason_text,
            valid_until=_parse_dt(body.valid_until) if body.valid_until else None,
        )
    except WatchlistError as exc:
        _handle(exc)
    return WatchlistItem(**detail)


@router.post("/watchlist/{entry_id}/deactivate", response_model=WatchlistItem)
def deactivate_entry(
    entry_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
) -> WatchlistItem:
    try:
        detail = deactivate_watchlist_entry(db, user, entry_id)
    except WatchlistError as exc:
        _handle(exc)
    return WatchlistItem(**detail)
