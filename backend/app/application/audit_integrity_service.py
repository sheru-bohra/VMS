"""Tamper-evident audit event sealing."""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.secret_validation import is_weak_secret
from app.domain.models import AuditEvent, AuditIntegrityChain


class AuditIntegrityError(Exception):
    pass


def _integrity_key() -> bytes:
    key = settings.audit_integrity_key
    if not key:
        raise AuditIntegrityError("Audit integrity key not configured.")
    return key.encode("utf-8")


def _canonical_payload(event: AuditEvent) -> str:
    payload = {
        "id": event.id,
        "actor_id": event.actor_id,
        "actor_email": event.actor_email,
        "action": event.action,
        "entity_type": event.entity_type,
        "entity_id": event.entity_id,
        "location_id": event.location_id,
        "metadata_json": event.metadata_json,
        "before_value": event.before_value,
        "after_value": event.after_value,
        "created_at": event.created_at.isoformat() if event.created_at else None,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _compute_hash(previous_hash: str, canonical: str, version: int) -> str:
    message = f"{version}|{previous_hash}|{canonical}".encode("utf-8")
    return hmac.new(_integrity_key(), message, hashlib.sha256).hexdigest()


def _get_or_create_chain(db: Session) -> AuditIntegrityChain:
    chain = db.query(AuditIntegrityChain).order_by(AuditIntegrityChain.id).first()
    if not chain:
        chain = AuditIntegrityChain(last_sequence=0, last_hash="", version=0)
        db.add(chain)
        db.flush()
    return chain


def seal_event(db: Session, event: AuditEvent) -> None:
    if not settings.audit_integrity_key or is_weak_secret(settings.audit_integrity_key, 16):
        return
    version = settings.audit_integrity_version
    for _ in range(5):
        chain = _get_or_create_chain(db)
        db.refresh(chain)
        previous = chain.last_hash or ""
        sequence = chain.last_sequence + 1
        canonical = _canonical_payload(event)
        digest = _compute_hash(previous, canonical, version)
        event.integrity_sequence = sequence
        event.previous_integrity_hash = previous
        event.integrity_hash = digest
        event.integrity_version = version
        chain.last_sequence = sequence
        chain.last_hash = digest
        chain.version = chain.version + 1
        chain.updated_at = datetime.now(timezone.utc)
        db.flush()
        return
    raise AuditIntegrityError("Failed to seal audit event due to concurrent chain update.")


def verify_chain(db: Session) -> Dict[str, Any]:
    if not settings.audit_integrity_key:
        return {"status": "UNCONFIGURED", "sealed_count": 0, "legacy_count": 0}

    events = (
        db.query(AuditEvent)
        .filter(AuditEvent.integrity_sequence.isnot(None))
        .order_by(AuditEvent.integrity_sequence.asc())
        .all()
    )
    legacy_count = db.query(AuditEvent).filter(AuditEvent.integrity_sequence.is_(None)).count()
    version = settings.audit_integrity_version
    expected_prev = ""
    expected_seq = 1
    for event in events:
        if event.integrity_sequence != expected_seq:
            return {
                "status": "BROKEN",
                "sealed_count": len(events),
                "legacy_count": legacy_count,
                "failed_sequence": expected_seq,
                "failed_event_id": event.id,
            }
        if event.previous_integrity_hash != expected_prev:
            return {
                "status": "BROKEN",
                "sealed_count": len(events),
                "legacy_count": legacy_count,
                "failed_sequence": event.integrity_sequence,
                "failed_event_id": event.id,
            }
        canonical = _canonical_payload(event)
        expected_hash = _compute_hash(expected_prev, canonical, event.integrity_version or version)
        if event.integrity_hash != expected_hash:
            return {
                "status": "BROKEN",
                "sealed_count": len(events),
                "legacy_count": legacy_count,
                "failed_sequence": event.integrity_sequence,
                "failed_event_id": event.id,
            }
        expected_prev = event.integrity_hash
        expected_seq += 1

    status = "VALID"
    if legacy_count > 0 and status == "VALID":
        status = "UNSEALED_LEGACY_EVENTS"
    return {
        "status": status,
        "sealed_count": len(events),
        "legacy_count": legacy_count,
        "last_verified_at": datetime.now(timezone.utc).isoformat(),
    }


def backfill_unsealed_events(db: Session, limit: int = 5000) -> int:
    if not settings.audit_integrity_key:
        raise AuditIntegrityError("Audit integrity key not configured.")
    unsealed = (
        db.query(AuditEvent)
        .filter(AuditEvent.integrity_sequence.is_(None))
        .order_by(AuditEvent.id.asc())
        .limit(limit)
        .all()
    )
    count = 0
    for event in unsealed:
        seal_event(db, event)
        count += 1
    return count
