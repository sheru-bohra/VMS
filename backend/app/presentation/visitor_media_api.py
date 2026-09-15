"""Protected visitor media access."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.application.auth_service import AuthContext
from app.application.visitor_media_service import VisitorMediaError, get_photo_for_view
from app.core.errors import APIError
from app.infrastructure.database import get_db
from app.presentation.dependencies import require_auth

router = APIRouter(tags=["visitor-media"])


def _handle(exc: VisitorMediaError) -> None:
    raise APIError(exc.status_code, exc.code, exc.message)


@router.get("/visitor-media/{media_id}/content")
def get_visitor_media_content(
    media_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
) -> Response:
    try:
        data, mime = get_photo_for_view(db, user, media_id)
    except VisitorMediaError as exc:
        _handle(exc)
    return Response(content=data, media_type=mime)
