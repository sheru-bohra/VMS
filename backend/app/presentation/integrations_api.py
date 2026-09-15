from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.application.auth_service import AuthContext
from app.core.config import settings
from app.domain.enums import NotificationStatus
from app.domain.models import Notification
from app.infrastructure.database import get_db
from app.presentation.dependencies import PermissionChecker
from app.domain.enums import Permission

router = APIRouter(prefix="/administration/integrations", tags=["administration"])


class IntegrationStatusResponse(BaseModel):
    entra_configured: bool
    graph_email_configured: bool = False
    graph_sender_mailbox: Optional[str] = None
    auth_mode: str
    email_provider: str
    last_successful_email_at: Optional[str] = None


@router.get("/status", response_model=IntegrationStatusResponse)
def integrations_status(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(PermissionChecker(Permission.ADMINS_MANAGE))],
) -> IntegrationStatusResponse:
    entra_ok = bool(settings.entra_tenant_id and settings.entra_client_id)
    last_sent = (
        db.query(func.max(Notification.sent_at))
        .filter(Notification.status == NotificationStatus.SENT.value)
        .scalar()
    )
    return IntegrationStatusResponse(
        entra_configured=entra_ok,
        graph_email_configured=False,
        graph_sender_mailbox=None,
        auth_mode=settings.auth_mode,
        email_provider=settings.email_provider,
        last_successful_email_at=last_sent.isoformat() if last_sent else None,
    )
