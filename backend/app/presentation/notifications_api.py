from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.application.auth_service import AuthContext
from app.application.notification_dispatch_service import dispatch_pending_notifications, retry_notification
from app.application.site_scope_service import apply_location_scope, get_allowed_location_ids
from app.core.config import settings
from app.core.errors import APIError
from app.domain.enums import Permission, role_has_permission
from app.domain.models import Notification
from app.infrastructure.database import get_db
from app.presentation.dependencies import require_auth
from app.presentation.schemas import NotificationItem, NotificationListResponse

router = APIRouter(tags=["notifications"])


def _require_read(ctx: AuthContext) -> None:
    if not role_has_permission(ctx.role, Permission.NOTIFICATION_READ):
        raise APIError(403, "forbidden", "Permission denied.")


def _require_manage(ctx: AuthContext) -> None:
    if not role_has_permission(ctx.role, Permission.NOTIFICATION_MANAGE):
        raise APIError(403, "forbidden", "Permission denied.")


def _to_item(n: Notification) -> NotificationItem:
    return NotificationItem(
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
        dev_action_url=n.dev_action_url if not settings.is_production else None,
        created_at=n.created_at.isoformat() if n.created_at else None,
    )


@router.get("/notifications", response_model=NotificationListResponse)
def list_notifications(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
    status: Annotated[Optional[str], Query()] = None,
    site: Annotated[Optional[int], Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> NotificationListResponse:
    _require_read(user)
    query = db.query(Notification)
    allowed = get_allowed_location_ids(user, db, site)
    if allowed is None:
        if site is not None:
            query = query.filter(Notification.location_id == site)
    elif not allowed:
        query = query.filter(Notification.id == -1)
    else:
        query = query.filter(Notification.location_id.in_(allowed))
    if status:
        query = query.filter(Notification.status == status.upper())
    total = query.count()
    rows = query.order_by(Notification.created_at.desc()).offset(offset).limit(limit).all()
    return NotificationListResponse(
        items=[_to_item(n) for n in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/notifications/{notification_id}", response_model=NotificationItem)
def get_notification(
    notification_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
) -> NotificationItem:
    _require_read(user)
    n = db.query(Notification).filter(Notification.id == notification_id).first()
    if not n:
        raise APIError(404, "not_found", "Notification not found.")
    if user.role.value != "GLOBAL_ADMIN" and user.role.value != "HEAD_ADMIN":
        from app.application.site_scope_service import can_access_location
        if n.location_id and not can_access_location(user, n.location_id):
            raise APIError(403, "forbidden", "Permission denied.")
    return _to_item(n)


@router.post("/notifications/{notification_id}/retry", response_model=NotificationItem)
def retry_notification_endpoint(
    notification_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
) -> NotificationItem:
    _require_manage(user)
    try:
        n = retry_notification(db, notification_id)
        dispatch_pending_notifications(db)
    except ValueError as exc:
        raise APIError(400, "retry_failed", str(exc))
    return _to_item(n)
