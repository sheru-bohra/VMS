from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.application.auth_service import AuthContext
from app.application.badge_service import BadgeError, get_badge_for_visit, issue_badge, record_print
from app.core.errors import APIError
from app.infrastructure.database import get_db
from app.presentation.dependencies import require_auth
from app.presentation.schemas import BadgeItem

router = APIRouter(tags=["badges"])


def _handle(exc: BadgeError) -> None:
    raise APIError(exc.status_code, exc.code, exc.message)


@router.get("/badges/visits/{visit_id}", response_model=BadgeItem)
def get_visit_badge(
    visit_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
) -> BadgeItem:
    try:
        detail = get_badge_for_visit(db, user, visit_id)
    except BadgeError as exc:
        _handle(exc)
    return BadgeItem(**detail)


@router.post("/badges/visits/{visit_id}/issue", response_model=BadgeItem)
def issue_visit_badge(
    visit_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
) -> BadgeItem:
    try:
        detail = issue_badge(db, user, visit_id)
    except BadgeError as exc:
        _handle(exc)
    return BadgeItem(**detail)


@router.post("/badges/visits/{visit_id}/print", response_model=BadgeItem)
def print_visit_badge(
    visit_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
) -> BadgeItem:
    try:
        detail = record_print(db, user, visit_id, reprint=True)
    except BadgeError as exc:
        _handle(exc)
    return BadgeItem(**detail)
