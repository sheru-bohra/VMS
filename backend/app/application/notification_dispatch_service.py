"""Dispatch pending notifications via email provider."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.application.audit_service import AuditService
from app.application.email_provider import get_email_provider
from app.application.notification_render_service import render_notification_email
from app.core.config import settings
from app.domain.enums import NotificationStatus
from app.domain.models import Notification


def dispatch_pending_notifications(db: Session, limit: int = 50) -> int:
    provider = get_email_provider()
    audit = AuditService(db)
    processed = 0
    pending = (
        db.query(Notification)
        .filter(Notification.status == NotificationStatus.PENDING.value)
        .order_by(Notification.created_at.asc())
        .limit(limit)
        .all()
    )

    for notification in pending:
        if notification.attempt_count >= settings.notification_max_attempts:
            notification.status = NotificationStatus.FAILED.value
            notification.failed_at = datetime.now(timezone.utc)
            notification.error_code = "MAX_ATTEMPTS"
            continue

        claimed = db.execute(
            update(Notification)
            .where(
                Notification.id == notification.id,
                Notification.status == NotificationStatus.PENDING.value,
            )
            .values(
                status=NotificationStatus.PROCESSING.value,
                attempt_count=notification.attempt_count + 1,
                last_attempt_at=datetime.now(timezone.utc),
            )
        )
        if claimed.rowcount == 0:
            continue

        db.refresh(notification)
        subject, body, html_body, attachments = render_notification_email(notification)
        from app.application.email_provider import EmailMessage
        result = provider.send(
            EmailMessage(
                to=notification.recipient,
                subject=subject,
                body=body,
                html_body=html_body,
                attachments=attachments or None,
            )
        )
        now = datetime.now(timezone.utc)
        if result.success:
            notification.status = NotificationStatus.SENT.value
            notification.sent_at = now
            notification.provider_message_id = result.provider_message_id
            audit.record(
                action="NOTIFICATION_SENT",
                entity_type="notification",
                entity_id=str(notification.id),
                location_id=notification.location_id,
                after_value={"type": notification.notification_type, "recipient": notification.recipient},
            )
        else:
            if notification.attempt_count >= settings.notification_max_attempts:
                notification.status = NotificationStatus.FAILED.value
                notification.failed_at = now
            else:
                notification.status = NotificationStatus.PENDING.value
            notification.error_code = result.error_code or "SEND_FAILED"
            audit.record(
                action="NOTIFICATION_FAILED",
                entity_type="notification",
                entity_id=str(notification.id),
                location_id=notification.location_id,
                after_value={"error": notification.error_code},
            )
        processed += 1

    db.commit()
    return processed


def retry_notification(db: Session, notification_id: int) -> Notification:
    notification = db.query(Notification).filter(Notification.id == notification_id).first()
    if not notification:
        raise ValueError("Notification not found")
    if notification.status not in (NotificationStatus.FAILED.value, NotificationStatus.PENDING.value):
        raise ValueError("Notification cannot be retried")
    notification.status = NotificationStatus.PENDING.value
    notification.error_code = None
    notification.failed_at = None
    AuditService(db).record(
        action="NOTIFICATION_RETRIED",
        entity_type="notification",
        entity_id=str(notification.id),
        location_id=notification.location_id,
    )
    db.commit()
    db.refresh(notification)
    return notification
