"""Upcoming visit reminder scheduling."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session, joinedload

from app.application.notification_dispatch_service import dispatch_pending_notifications
from app.application.notification_service import queue_upcoming_reminder_email
from app.core.config import settings
from app.domain.enums import VisitSource, VisitStatus
from app.domain.models import Host, Visit, Visitor


def process_upcoming_reminders(db: Session) -> int:
    now = datetime.now(timezone.utc)
    window_end = now + timedelta(minutes=settings.upcoming_visit_reminder_minutes)
    window_start = now

    visits = (
        db.query(Visit)
        .options(
            joinedload(Visit.visitor),
            joinedload(Visit.location),
            joinedload(Visit.host),
        )
        .filter(
            Visit.source == VisitSource.ADVANCE_REGISTRATION.value,
            Visit.status == VisitStatus.APPROVED.value,
            Visit.scheduled_start.isnot(None),
            Visit.scheduled_start >= window_start,
            Visit.scheduled_start <= window_end,
        )
        .all()
    )

    queued = 0
    for visit in visits:
        if not visit.host_id:
            continue
        host = visit.host or db.query(Host).filter(Host.id == visit.host_id).first()
        if not host or not host.email:
            continue
        scheduled_display = visit.scheduled_start.strftime("%I:%M %p") if visit.scheduled_start else "—"
        payload = {
            "visitor_name": visit.visitor.full_name if visit.visitor else "",
            "company": visit.visitor.company if visit.visitor else None,
            "site_name": visit.location.name if visit.location else "",
            "purpose": visit.purpose,
            "scheduled_display": scheduled_display,
        }
        notification = queue_upcoming_reminder_email(
            db,
            visit_id=visit.id,
            host_id=visit.host_id,
            host_email=host.email,
            location_id=visit.location_id,
            payload=payload,
        )
        if notification:
            queued += 1

    if queued:
        db.commit()
    return queued


def run_scheduler_cycle(db: Session) -> None:
    process_upcoming_reminders(db)
    dispatch_pending_notifications(db)
