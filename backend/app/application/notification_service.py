"""Notification queue and lifecycle."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.application.audit_service import AuditService
from app.application.notification_templates import TEMPLATE_RENDERERS
from app.core.config import settings
from app.domain.enums import NotificationChannel, NotificationStatus, NotificationType
from app.domain.models import Notification


class NotificationError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _render(template_key: str, payload: Dict[str, Any]) -> tuple[str, str]:
    renderer = TEMPLATE_RENDERERS.get(template_key)
    if not renderer:
        return "VMS Notification", json.dumps(payload)
    return renderer(payload)


def queue_notification(
    db: Session,
    notification_type: str,
    recipient: str,
    template_key: str,
    payload: Dict[str, Any],
    dedupe_key: str,
    visit_id: Optional[int] = None,
    host_id: Optional[int] = None,
    location_id: Optional[int] = None,
    dev_action_url: Optional[str] = None,
    audit_action: Optional[str] = None,
) -> Optional[Notification]:
    existing = db.query(Notification.id).filter(Notification.dedupe_key == dedupe_key).first()
    if existing:
        return None

    subject, body = _render(template_key, payload)
    notification = Notification(
        notification_type=notification_type,
        channel=NotificationChannel.EMAIL.value,
        recipient=recipient,
        visit_id=visit_id,
        host_id=host_id,
        location_id=location_id,
        status=NotificationStatus.PENDING.value,
        subject=subject,
        template_key=template_key,
        payload_json=json.dumps(payload),
        dedupe_key=dedupe_key,
        attempt_count=0,
        body_preview=body,
        dev_action_url=dev_action_url if not settings.is_production else None,
    )
    db.add(notification)
    db.flush()

    if audit_action:
        audit = AuditService(db)
        audit.record(
            action=audit_action,
            entity_type="notification",
            entity_id=str(notification.id),
            location_id=location_id,
            after_value={
                "type": notification_type,
                "recipient": recipient,
                "visit_id": visit_id,
            },
        )
    return notification


def queue_host_approval_request_email(
    db: Session,
    visit_id: int,
    host_id: int,
    host_email: str,
    request_id: int,
    payload: Dict[str, Any],
    dev_action_url: Optional[str] = None,
    is_resend: bool = False,
) -> Optional[Notification]:
    dedupe = f"HOST_APPROVAL_REQUEST:{request_id}"
    action = "HOST_APPROVAL_REQUEST_RESENT" if is_resend else "HOST_APPROVAL_REQUEST_SENT"
    return queue_notification(
        db,
        notification_type=NotificationType.HOST_APPROVAL_REQUEST.value,
        recipient=host_email,
        template_key="host_approval_request",
        payload=payload,
        dedupe_key=dedupe,
        visit_id=visit_id,
        host_id=host_id,
        location_id=payload.get("location_id"),
        dev_action_url=dev_action_url,
        audit_action=action,
    )


def queue_visitor_arrived_email(
    db: Session,
    visit_id: int,
    host_id: int,
    host_email: str,
    location_id: int,
    payload: Dict[str, Any],
) -> Optional[Notification]:
    return queue_notification(
        db,
        notification_type=NotificationType.VISITOR_ARRIVED.value,
        recipient=host_email,
        template_key="visitor_arrived",
        payload=payload,
        dedupe_key=f"VISITOR_ARRIVED:{visit_id}",
        visit_id=visit_id,
        host_id=host_id,
        location_id=location_id,
        audit_action="HOST_ARRIVAL_NOTIFICATION_QUEUED",
    )


def queue_visitor_invitation_email(
    db: Session,
    visit_id: int,
    visitor_email: str,
    location_id: int,
    payload: Dict[str, Any],
    invitation_version: str,
) -> Optional[Notification]:
    email = (visitor_email or "").strip()
    if not email or "@" not in email:
        return None
    return queue_notification(
        db,
        notification_type=NotificationType.VISITOR_INVITATION.value,
        recipient=email,
        template_key="visitor_invitation",
        payload=payload,
        dedupe_key=f"VISITOR_INVITATION:{visit_id}:{invitation_version}",
        visit_id=visit_id,
        location_id=location_id,
        audit_action="VISITOR_INVITATION_QUEUED",
    )


def queue_upcoming_reminder_email(
    db: Session,
    visit_id: int,
    host_id: int,
    host_email: str,
    location_id: int,
    payload: Dict[str, Any],
) -> Optional[Notification]:
    return queue_notification(
        db,
        notification_type=NotificationType.UPCOMING_VISIT_REMINDER.value,
        recipient=host_email,
        template_key="upcoming_visit_reminder",
        payload=payload,
        dedupe_key=f"UPCOMING_REMINDER:{visit_id}",
        visit_id=visit_id,
        host_id=host_id,
        location_id=location_id,
        audit_action="UPCOMING_VISIT_REMINDER_QUEUED",
    )


def cancel_pending_notifications_for_visit(db: Session, visit_id: int, notification_type: Optional[str] = None) -> None:
    query = db.query(Notification).filter(
        Notification.visit_id == visit_id,
        Notification.status == NotificationStatus.PENDING.value,
    )
    if notification_type:
        query = query.filter(Notification.notification_type == notification_type)
    now = datetime.now(timezone.utc)
    for row in query.all():
        row.status = NotificationStatus.CANCELLED.value
        row.failed_at = now
