"""Background processor for physical access and badge print integrations."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.application.access_provisioning_service import (
    process_expired_credentials,
    process_pending_access_attempts,
    reconcile_checked_out_active_credentials,
)
from app.application.physical_badge_print_service import process_print_jobs
from app.core.config import settings

logger = logging.getLogger(__name__)


def run_physical_integration_cycle(db: Session) -> None:
    if not settings.physical_integration_scheduler_enabled:
        return
    try:
        process_pending_access_attempts(db)
        reconcile_checked_out_active_credentials(db)
        process_expired_credentials(db)
        process_print_jobs(db)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Physical integration scheduler cycle failed")
