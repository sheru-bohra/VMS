from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.runtime_instance import get_runtime_instance_id
from app.domain.models import RuntimeLease


class SchedulerLeaseError(Exception):
    pass


DEFAULT_LEASE_SECONDS = 120


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class SchedulerLeaseService:
    def __init__(self, db: Session):
        self._db = db
        self._owner = get_runtime_instance_id()

    def try_acquire_or_renew(self, lease_name: str, lease_seconds: int = DEFAULT_LEASE_SECONDS) -> bool:
        now = datetime.now(timezone.utc)
        until = now + timedelta(seconds=lease_seconds)
        lease = (
            self._db.query(RuntimeLease)
            .filter(RuntimeLease.lease_name == lease_name)
            .with_for_update()
            .first()
        )
        if lease is None:
            lease = RuntimeLease(
                lease_name=lease_name,
                owner_id=self._owner,
                leased_until=until,
                heartbeat_at=now,
                version=1,
            )
            self._db.add(lease)
            try:
                self._db.flush()
            except IntegrityError:
                self._db.rollback()
                return False
            return True
        if lease.owner_id == self._owner or _as_utc(lease.leased_until) <= now:
            lease.owner_id = self._owner
            lease.leased_until = until
            lease.heartbeat_at = now
            lease.version = (lease.version or 0) + 1
            self._db.flush()
            return True
        return False

    def release_lease(self, lease_name: str) -> None:
        lease = self._db.query(RuntimeLease).filter(RuntimeLease.lease_name == lease_name).first()
        if lease and lease.owner_id == self._owner:
            lease.leased_until = datetime.now(timezone.utc)
            lease.heartbeat_at = datetime.now(timezone.utc)
            self._db.flush()

    def release_all_owned(self) -> int:
        now = datetime.now(timezone.utc)
        leases = self._db.query(RuntimeLease).filter(RuntimeLease.owner_id == self._owner).all()
        for lease in leases:
            lease.leased_until = now
            lease.heartbeat_at = now
        self._db.flush()
        return len(leases)

    def mark_cycle_started(self, lease_name: str) -> None:
        lease = self._db.query(RuntimeLease).filter(RuntimeLease.lease_name == lease_name).first()
        if lease:
            lease.last_cycle_started_at = datetime.now(timezone.utc)
            self._db.flush()

    def mark_cycle_success(self, lease_name: str) -> None:
        now = datetime.now(timezone.utc)
        lease = self._db.query(RuntimeLease).filter(RuntimeLease.lease_name == lease_name).first()
        if lease:
            lease.last_cycle_completed_at = now
            lease.last_success_at = now
            lease.last_error_code = None
            self._db.flush()

    def mark_cycle_error(self, lease_name: str, error_code: str) -> None:
        now = datetime.now(timezone.utc)
        lease = self._db.query(RuntimeLease).filter(RuntimeLease.lease_name == lease_name).first()
        if lease:
            lease.last_cycle_completed_at = now
            lease.last_error_code = error_code
            self._db.flush()

    def get_lease_status(self, lease_name: str) -> Optional[Dict[str, Any]]:
        lease = self._db.query(RuntimeLease).filter(RuntimeLease.lease_name == lease_name).first()
        if not lease:
            return None
        now = datetime.now(timezone.utc)
        owned_by_self = lease.owner_id == self._owner and _as_utc(lease.leased_until) > now
        return {
            "lease_name": lease.lease_name,
            "state": "ACTIVE" if _as_utc(lease.leased_until) > now else "STANDBY",
            "owned_by_self": owned_by_self,
            "lease_expires_at": lease.leased_until.isoformat() if lease.leased_until else None,
            "last_cycle_started_at": lease.last_cycle_started_at.isoformat() if lease.last_cycle_started_at else None,
            "last_cycle_completed_at": lease.last_cycle_completed_at.isoformat() if lease.last_cycle_completed_at else None,
            "last_success_at": lease.last_success_at.isoformat() if lease.last_success_at else None,
            "last_error_code": lease.last_error_code,
            "owner_masked": f"inst-{lease.owner_id[:8]}" if lease.owner_id else None,
        }
