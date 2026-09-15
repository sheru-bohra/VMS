"""Scheduled automated data retention (production opt-in)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.application.data_retention_service import execute_policy_scheduled
from app.core.config import settings
from app.domain.models import DataRetentionPolicy, DataRetentionRunDedupe

logger = logging.getLogger(__name__)


def run_retention_automation_cycle(db: Session) -> None:
    if not settings.retention_automation_enabled:
        return
    today = datetime.now(timezone.utc).date().isoformat()
    policies = db.query(DataRetentionPolicy).filter(DataRetentionPolicy.is_active.is_(True)).all()
    for policy in policies:
        existing = (
            db.query(DataRetentionRunDedupe)
            .filter(
                DataRetentionRunDedupe.policy_id == policy.id,
                DataRetentionRunDedupe.scheduled_date == today,
            )
            .first()
        )
        if existing:
            continue
        dedupe = DataRetentionRunDedupe(policy_id=policy.id, scheduled_date=today)
        db.add(dedupe)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            continue
        try:
            result = execute_policy_scheduled(db, policy.id)
            dedupe.run_id = result.get("run_id")
            db.commit()
            logger.info(
                "Automated retention completed policy_id=%s processed=%s",
                policy.id,
                result.get("processed_count"),
            )
        except Exception:
            db.rollback()
            logger.exception("Automated retention failed policy_id=%s", policy.id)
