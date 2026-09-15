from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.application.auth_service import AuthContext
from app.application.security_review_service import (
    SecurityReviewError,
    get_security_review,
    list_security_reviews,
    resolve_block,
    resolve_clear,
)
from app.core.errors import APIError
from app.infrastructure.database import get_db
from app.presentation.dependencies import require_auth
from app.presentation.schemas import (
    SecurityBlockRequest,
    SecurityResolveRequest,
    SecurityReviewItem,
    SecurityReviewListResponse,
)

router = APIRouter(tags=["security-reviews"])


def _handle(exc: SecurityReviewError) -> None:
    raise APIError(exc.status_code, exc.code, exc.message)


@router.get("/security-reviews", response_model=SecurityReviewListResponse)
def list_reviews(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
    tab: Annotated[Optional[str], Query()] = None,
    search: Annotated[Optional[str], Query(max_length=100)] = None,
    site: Annotated[Optional[int], Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SecurityReviewListResponse:
    try:
        items, total, review_count, blocked_count = list_security_reviews(
            db, user, tab=tab, search=search, site=site, limit=limit, offset=offset,
        )
    except SecurityReviewError as exc:
        _handle(exc)
    return SecurityReviewListResponse(
        items=[SecurityReviewItem(**item) for item in items],
        total=total,
        review_count=review_count,
        blocked_count=blocked_count,
        limit=limit,
        offset=offset,
    )


@router.get("/security-reviews/{visit_id}", response_model=SecurityReviewItem)
def get_review(
    visit_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
) -> SecurityReviewItem:
    try:
        detail = get_security_review(db, user, visit_id)
    except SecurityReviewError as exc:
        _handle(exc)
    return SecurityReviewItem(**detail)


@router.post("/security-reviews/{visit_id}/clear", response_model=SecurityReviewItem)
def clear_review(
    visit_id: int,
    body: SecurityResolveRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
) -> SecurityReviewItem:
    try:
        detail = resolve_clear(db, user, visit_id, comment=body.comment)
    except SecurityReviewError as exc:
        _handle(exc)
    return SecurityReviewItem(**detail)


@router.post("/security-reviews/{visit_id}/block", response_model=SecurityReviewItem)
def block_review(
    visit_id: int,
    body: SecurityBlockRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
) -> SecurityReviewItem:
    try:
        detail = resolve_block(db, user, visit_id, comment=body.comment)
    except SecurityReviewError as exc:
        _handle(exc)
    return SecurityReviewItem(**detail)
