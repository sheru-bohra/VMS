from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.application.auth_service import AuthContext
from app.application.visitor_qr_service import QrVerifyError, verify_by_reference, verify_by_token
from app.core.errors import APIError
from app.infrastructure.database import get_db
from app.presentation.dependencies import require_auth
from app.presentation.schemas import QrVerifyRequest, QrVerifyResponse

router = APIRouter(tags=["scanner"])


def _handle(exc: QrVerifyError) -> None:
    raise APIError(exc.status_code, exc.code, exc.message)


@router.post("/visitor-qr/verify", response_model=QrVerifyResponse)
def verify_visitor_qr(
    body: QrVerifyRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
) -> QrVerifyResponse:
    try:
        if body.token and body.token.strip():
            result = verify_by_token(db, user, body.token.strip())
        elif body.registration_reference and body.registration_reference.strip():
            result = verify_by_reference(db, user, body.registration_reference.strip())
        else:
            raise APIError(422, "validation_error", "Token or registration reference is required.")
    except QrVerifyError as exc:
        _handle(exc)
    return QrVerifyResponse(**result)
