"""Expanded PostgreSQL live validation when TEST_POSTGRES_URL is configured."""

import threading

import pytest
from sqlalchemy.orm import sessionmaker

from app.application.audit_integrity_service import verify_chain
from app.application.release_evidence import record_live_result
from app.application.scheduler_lease_service import SchedulerLeaseService
from app.core import runtime_instance
from app.domain.models import RuntimeLease
from app.domain.release_status import IntegrationReleaseStatus


def test_postgres_scheduler_lease_failover(postgres_engine):
    Session = sessionmaker(bind=postgres_engine)
    runtime_instance._runtime_instance_id = "pg-inst-a"
    db = Session()
    svc = SchedulerLeaseService(db)
    assert svc.try_acquire_or_renew("notification-dispatch", lease_seconds=60)
    db.commit()
    runtime_instance._runtime_instance_id = "pg-inst-b"
    assert not SchedulerLeaseService(db).try_acquire_or_renew("notification-dispatch")
    db.rollback()
    lease = db.query(RuntimeLease).filter(RuntimeLease.lease_name == "notification-dispatch").first()
    from datetime import datetime, timedelta, timezone

    lease.leased_until = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()
    assert SchedulerLeaseService(db).try_acquire_or_renew("notification-dispatch")
    db.commit()
    db.close()
    record_live_result("postgresql", IntegrationReleaseStatus.LIVE_VALIDATED, "scheduler_lease=PASS")


def test_postgres_audit_integrity_under_load(postgres_engine):
    Session = sessionmaker(bind=postgres_engine)
    errors = []

    def worker():
        db = Session()
        try:
            from app.application.audit_service import AuditService

            AuditService(db).record(
                action="UAT_CONCURRENT",
                entity_type="TEST",
                entity_id="pg-live",
                metadata={"marker": "postgres_live"},
            )
            db.commit()
        except Exception as exc:
            errors.append(str(exc))
        finally:
            db.close()

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors, errors
    db = Session()
    result = verify_chain(db)
    db.close()
    assert result.get("status") == "VALID"
    record_live_result("audit_integrity", IntegrationReleaseStatus.LIVE_VALIDATED, "concurrent_append=VALID")
