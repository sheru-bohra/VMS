from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.application.copilot_service import CopilotError, get_suggested_questions, process_copilot_query
from app.application.rate_limit_service import check_ai_copilot_rate_limit, check_ai_insight_refresh_rate_limit
from app.application.visitor_intelligence_service import IntelligenceError, dismiss_insight, list_insights, refresh_insights
from app.application.auth_service import AuthContext
from app.core.errors import APIError
from app.infrastructure.database import get_db
from app.presentation.dependencies import require_auth

router = APIRouter(tags=["ai"])


class CopilotQueryBody(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    location_id: Optional[int] = None
    session_id: Optional[int] = None


def _copilot_err(exc: CopilotError) -> None:
    raise APIError(exc.status_code, exc.code, exc.message)


def _intel_err(exc: IntelligenceError) -> None:
    raise APIError(exc.status_code, exc.code, exc.message)


@router.get("/ai/copilot/suggestions")
def copilot_suggestions(user: Annotated[AuthContext, Depends(require_auth)]):
    return {"suggestions": get_suggested_questions(user)}


@router.post("/ai/copilot/query")
def copilot_query(
    body: CopilotQueryBody,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
):
    check_ai_copilot_rate_limit(user.email)
    try:
        return process_copilot_query(
            db, user, body.question, location_id=body.location_id, session_id=body.session_id,
        )
    except CopilotError as exc:
        _copilot_err(exc)


@router.get("/ai/insights")
def get_insights(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
    location_id: Annotated[Optional[int], Query()] = None,
    priority: Annotated[Optional[str], Query()] = None,
    insight_type: Annotated[Optional[str], Query()] = None,
    status: Annotated[Optional[str], Query()] = "ACTIVE",
):
    try:
        items = list_insights(db, user, location_id=location_id, priority=priority, insight_type=insight_type, status=status)
    except IntelligenceError as exc:
        _intel_err(exc)
    return {"items": items}


@router.post("/ai/insights/refresh")
def insights_refresh(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
    location_id: Annotated[Optional[int], Query()] = None,
):
    check_ai_insight_refresh_rate_limit(user.email)
    try:
        count = refresh_insights(db, user, location_id=location_id)
    except IntelligenceError as exc:
        _intel_err(exc)
    return {"generated": count}


@router.post("/ai/insights/{insight_id}/dismiss")
def insights_dismiss(
    insight_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
):
    try:
        return dismiss_insight(db, user, insight_id)
    except IntelligenceError as exc:
        _intel_err(exc)
