"""Run scheduler workloads guarded by database-backed leases."""

from __future__ import annotations

import logging
from typing import Callable

from sqlalchemy.orm import Session

from app.application.scheduler_lease_service import SchedulerLeaseService

logger = logging.getLogger(__name__)

LEASE_NOTIFICATION_DISPATCH = "notification-dispatch"
LEASE_UPCOMING_REMINDERS = "upcoming-reminders"
LEASE_VISITOR_INTELLIGENCE = "visitor-intelligence"
LEASE_DATA_RETENTION = "data-retention"
LEASE_PHYSICAL_INTEGRATIONS = "physical-integrations"

ALL_SCHEDULER_LEASES = (
    LEASE_NOTIFICATION_DISPATCH,
    LEASE_UPCOMING_REMINDERS,
    LEASE_VISITOR_INTELLIGENCE,
    LEASE_DATA_RETENTION,
    LEASE_PHYSICAL_INTEGRATIONS,
)


def run_with_scheduler_lease(db: Session, lease_name: str, work: Callable[[Session], None]) -> bool:
    """Acquire or renew lease, run work, record cycle outcome. Returns False if lease not held."""
    lease_svc = SchedulerLeaseService(db)
    try:
        if not lease_svc.try_acquire_or_renew(lease_name):
            db.rollback()
            return False
        db.commit()
        lease_svc.mark_cycle_started(lease_name)
        db.commit()
        work(db)
        lease_svc.mark_cycle_success(lease_name)
        db.commit()
        return True
    except Exception:
        logger.exception("Scheduler cycle failed lease=%s", lease_name)
        try:
            lease_svc.mark_cycle_error(lease_name, "SCHEDULER_CYCLE_FAILED")
            db.commit()
        except Exception:
            db.rollback()
        raise
