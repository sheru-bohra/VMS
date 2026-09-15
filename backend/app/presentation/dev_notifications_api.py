from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.application.auth_service import AuthContext
from app.core.config import settings
from app.core.errors import APIError
from app.domain.enums import AdminRole
from app.domain.models import Notification
from app.infrastructure.database import get_db
from app.presentation.dependencies import require_auth
from app.presentation.schemas import NotificationItem, NotificationListResponse

router = APIRouter(tags=["dev-notifications"])


def _require_dev_global_admin(user: AuthContext) -> None:
    if settings.is_production:
        raise APIError(404, "not_found", "Not found.")
    if user.role != AdminRole.GLOBAL_ADMIN:
        raise APIError(403, "forbidden", "Permission denied.")


@router.get("/dev/notifications", response_model=NotificationListResponse)
def list_dev_notifications(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
) -> NotificationListResponse:
    _require_dev_global_admin(user)
    rows = db.query(Notification).order_by(Notification.created_at.desc()).limit(100).all()
    items = [
        NotificationItem(
            id=n.id,
            notification_type=n.notification_type,
            channel=n.channel,
            recipient=n.recipient,
            visit_id=n.visit_id,
            host_id=n.host_id,
            location_id=n.location_id,
            status=n.status,
            subject=n.subject,
            template_key=n.template_key,
            attempt_count=n.attempt_count,
            sent_at=n.sent_at.isoformat() if n.sent_at else None,
            failed_at=n.failed_at.isoformat() if n.failed_at else None,
            error_code=n.error_code,
            body_preview=n.body_preview,
            dev_action_url=n.dev_action_url,
            created_at=n.created_at.isoformat() if n.created_at else None,
        )
        for n in rows
    ]
    return NotificationListResponse(items=items, total=len(items), limit=100, offset=0)
