"""Data retention policy resolution and safe execution."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.application.identity_normalization import normalize_email, normalize_mobile, normalize_person_name
from app.application.audit_service import AuditService
from app.application.auth_service import AuthContext
from app.application.document_storage import document_storage
from app.domain.enums import AdminRole, Permission, VisitStatus, role_has_permission
from app.domain.models import (
    AIInteraction,
    ComplianceDocument,
    DataRetentionPolicy,
    DataRetentionRun,
    DataRetentionRunDedupe,
    EmergencyEvent,
    EmergencyRollCallEntry,
    Location,
    Notification,
    SecurityScreening,
    Visit,
    Visitor,
    WatchlistEntry,
)

RETENTION_CATEGORIES = frozenset({
    "VISITOR_PII",
    "VISIT_FREE_TEXT",
    "NOTIFICATION_CONTENT",
    "AI_INTERACTION",
    "COMPLIANCE_DOCUMENT_FILE",
    "EMERGENCY_SNAPSHOT_PII",
})

RETENTION_ACTIONS = frozenset({"ANONYMIZE", "PURGE_CONTENT", "DELETE_FILE"})

ACTIVE_VISIT_STATUSES = frozenset({
    VisitStatus.PENDING_APPROVAL.value,
    VisitStatus.APPROVED.value,
    VisitStatus.EXPECTED.value,
    VisitStatus.ARRIVED.value,
    VisitStatus.CHECKED_IN.value,
    VisitStatus.ONSITE.value,
})

PURGED_PLACEHOLDER = "[Removed by retention policy]"
ANONYMIZED_NAME = "Anonymized Visitor"


class RetentionError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _require_read(ctx: AuthContext) -> None:
    if not role_has_permission(ctx.role, Permission.PRIVACY_RETENTION_READ):
        raise RetentionError("forbidden", "Permission denied.", 403)


def _require_manage(ctx: AuthContext) -> None:
    if not role_has_permission(ctx.role, Permission.PRIVACY_RETENTION_MANAGE):
        raise RetentionError("forbidden", "Permission denied.", 403)


def _require_execute(ctx: AuthContext) -> None:
    if not role_has_permission(ctx.role, Permission.PRIVACY_RETENTION_EXECUTE):
        raise RetentionError("forbidden", "Permission denied.", 403)


def resolve_policy(db: Session, category: str, location_id: Optional[int] = None) -> Optional[DataRetentionPolicy]:
    if location_id:
        loc_policy = (
            db.query(DataRetentionPolicy)
            .filter(
                DataRetentionPolicy.data_category == category,
                DataRetentionPolicy.scope_type == "LOCATION",
                DataRetentionPolicy.location_id == location_id,
                DataRetentionPolicy.is_active.is_(True),
            )
            .first()
        )
        if loc_policy:
            return loc_policy
    return (
        db.query(DataRetentionPolicy)
        .filter(
            DataRetentionPolicy.data_category == category,
            DataRetentionPolicy.scope_type == "GLOBAL",
            DataRetentionPolicy.is_active.is_(True),
        )
        .first()
    )


def list_policies(db: Session, ctx: AuthContext) -> List[Dict[str, Any]]:
    _require_read(ctx)
    policies = db.query(DataRetentionPolicy).order_by(DataRetentionPolicy.data_category).all()
    return [_policy_dict(p, db) for p in policies]


def _policy_dict(p: DataRetentionPolicy, db: Session) -> Dict[str, Any]:
    loc_name = None
    if p.location_id:
        loc = db.query(Location).filter(Location.id == p.location_id).first()
        loc_name = loc.name if loc else None
    return {
        "id": p.id,
        "data_category": p.data_category,
        "scope_type": p.scope_type,
        "location_id": p.location_id,
        "location_name": loc_name,
        "retention_days": p.retention_days,
        "action": p.action,
        "is_active": p.is_active,
    }


def create_policy(
    db: Session,
    ctx: AuthContext,
    data_category: str,
    scope_type: str,
    retention_days: int,
    action: str,
    location_id: Optional[int] = None,
) -> Dict[str, Any]:
    _require_manage(ctx)
    if data_category not in RETENTION_CATEGORIES:
        raise RetentionError("invalid_category", "Invalid data category.")
    if action not in RETENTION_ACTIONS:
        raise RetentionError("invalid_action", "Invalid retention action.")
    if retention_days < 1 or retention_days > 3650:
        raise RetentionError("invalid_days", "Retention days must be between 1 and 3650.")
    if scope_type == "LOCATION" and not location_id:
        raise RetentionError("location_required", "Location is required for location-scoped policy.")
    existing = (
        db.query(DataRetentionPolicy)
        .filter(
            DataRetentionPolicy.data_category == data_category,
            DataRetentionPolicy.scope_type == scope_type,
            DataRetentionPolicy.location_id == location_id if scope_type == "LOCATION" else None,
        )
        .first()
    )
    if existing:
        raise RetentionError("duplicate_policy", "A policy for this category and scope already exists.")
    policy = DataRetentionPolicy(
        data_category=data_category,
        scope_type=scope_type,
        location_id=location_id if scope_type == "LOCATION" else None,
        retention_days=retention_days,
        action=action,
        is_active=True,
        created_by_user_id=ctx.user_id,
        updated_by_user_id=ctx.user_id,
    )
    db.add(policy)
    db.flush()
    AuditService(db).record(
        action="RETENTION_POLICY_CREATED",
        entity_type="data_retention_policy",
        entity_id=str(policy.id),
        actor_id=ctx.user_id,
        actor_email=ctx.email,
        after_value={"category": data_category, "days": retention_days},
    )
    return _policy_dict(policy, db)


def _cutoff(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


def _visitor_has_active_dependency(db: Session, visitor_id: int) -> bool:
    now = datetime.now(timezone.utc)
    active = (
        db.query(Visit.id)
        .filter(
            Visit.visitor_id == visitor_id,
            Visit.status.in_(list(ACTIVE_VISIT_STATUSES)),
        )
        .first()
    )
    if active:
        return True
    future = (
        db.query(Visit.id)
        .filter(Visit.visitor_id == visitor_id, Visit.scheduled_start.isnot(None), Visit.scheduled_start > now)
        .first()
    )
    return future is not None


def _visitor_has_active_security_dependency(db: Session, visitor_id: int) -> bool:
    pending = (
        db.query(SecurityScreening.id)
        .filter(
            SecurityScreening.visitor_id == visitor_id,
            SecurityScreening.resolved_at.is_(None),
            SecurityScreening.outcome.in_(["REVIEW", "BLOCKED"]),
        )
        .first()
    )
    return pending is not None


def _visitor_has_active_watchlist_dependency(db: Session, visitor: Visitor) -> bool:
    q = db.query(WatchlistEntry.id).filter(WatchlistEntry.status == "ACTIVE")
    v_mobile = normalize_mobile(visitor.phone)
    if v_mobile:
        match = q.filter(WatchlistEntry.normalized_mobile == v_mobile).first()
        if match:
            return True
    if visitor.email:
        v_email = normalize_email(visitor.email)
        match = q.filter(WatchlistEntry.normalized_email == v_email).first()
        if match:
            return True
    v_name = normalize_person_name(visitor.full_name)
    match = q.filter(WatchlistEntry.normalized_name == v_name).first()
    if match:
        return True
    return False


def _visitor_retention_blocked(db: Session, visitor_id: int) -> bool:
    if _visitor_has_active_dependency(db, visitor_id):
        return True
    visitor = db.query(Visitor).filter(Visitor.id == visitor_id).first()
    if not visitor:
        return True
    if _visitor_has_active_security_dependency(db, visitor_id):
        return True
    if _visitor_has_active_watchlist_dependency(db, visitor):
        return True
    return False


def _eligible_visitor_pii(db: Session, policy: DataRetentionPolicy) -> Tuple[List[int], List[int]]:
    cutoff = _cutoff(policy.retention_days)
    q = db.query(Visitor).filter(Visitor.privacy_state != "ANONYMIZED")
    if policy.scope_type == "LOCATION" and policy.location_id:
        q = q.join(Visit).filter(Visit.location_id == policy.location_id).distinct()
    eligible: List[int] = []
    skipped: List[int] = []
    for visitor in q.all():
        if _visitor_retention_blocked(db, visitor.id):
            skipped.append(visitor.id)
            continue
        latest_end = (
            db.query(func.max(Visit.updated_at))
            .filter(Visit.visitor_id == visitor.id)
            .scalar()
        )
        if not latest_end:
            skipped.append(visitor.id)
            continue
        if latest_end.tzinfo is None:
            latest_end = latest_end.replace(tzinfo=timezone.utc)
        if latest_end > cutoff:
            skipped.append(visitor.id)
            continue
        eligible.append(visitor.id)
    return eligible, skipped


def _anonymize_visitor(db: Session, visitor_id: int, actor: AuthContext) -> bool:
    visitor = db.query(Visitor).filter(Visitor.id == visitor_id).first()
    if not visitor or visitor.privacy_state == "ANONYMIZED":
        return False
    if _visitor_retention_blocked(db, visitor_id):
        return False
    visitor.full_name = ANONYMIZED_NAME
    visitor.phone = None
    visitor.email = None
    visitor.company = None
    visitor.privacy_state = "ANONYMIZED"
    visitor.anonymized_at = datetime.now(timezone.utc)
    AuditService(db).record(
        action="VISITOR_PII_ANONYMIZED",
        entity_type="visitor",
        entity_id=str(visitor_id),
        actor_id=actor.user_id if actor else None,
        actor_email=actor.email if actor else None,
    )
    return True


def _purge_visit_free_text(db: Session, visit_id: int) -> bool:
    visit = db.query(Visit).filter(Visit.id == visit_id).first()
    if not visit:
        return False
    changed = False
    if visit.purpose and visit.purpose != PURGED_PLACEHOLDER:
        visit.purpose = PURGED_PLACEHOLDER
        changed = True
    if visit.notes and visit.notes != PURGED_PLACEHOLDER:
        visit.notes = PURGED_PLACEHOLDER
        changed = True
    return changed


def _purge_notification(db: Session, notification_id: int) -> bool:
    n = db.query(Notification).filter(Notification.id == notification_id).first()
    if not n:
        return False
    if n.body_preview == PURGED_PLACEHOLDER:
        return False
    n.recipient = "purged@invalid.local"
    n.subject = PURGED_PLACEHOLDER
    n.body_preview = PURGED_PLACEHOLDER
    n.payload_json = "{}"
    n.dev_action_url = None
    return True


def _purge_ai_interaction(db: Session, interaction_id: int) -> bool:
    row = db.query(AIInteraction).filter(AIInteraction.id == interaction_id).first()
    if not row:
        return False
    if not row.question_redacted and not row.response_summary and not row.location_scope_json:
        return False
    row.question_redacted = None
    row.response_summary = None
    row.location_scope_json = None
    return True


def _purge_compliance_file(db: Session, doc_id: int, actor: AuthContext) -> bool:
    doc = db.query(ComplianceDocument).filter(ComplianceDocument.id == doc_id).first()
    if not doc or doc.storage_state == "PURGED":
        return False
    deleted = document_storage.delete_file(doc.storage_key)
    doc.storage_state = "PURGED"
    doc.purged_at = datetime.now(timezone.utc)
    doc.file_name = f"purged-{doc.id}.dat"
    if not deleted:
        return False
    AuditService(db).record(
        action="COMPLIANCE_FILE_PURGED",
        entity_type="compliance_document",
        entity_id=str(doc_id),
        actor_id=actor.user_id if actor else None,
        actor_email=actor.email if actor else None,
    )
    return True


def _anonymize_emergency_snapshot(db: Session, event_id: int, actor: AuthContext) -> int:
    event = db.query(EmergencyEvent).filter(EmergencyEvent.id == event_id).first()
    if not event or event.status != "CLOSED":
        return 0
    entries = db.query(EmergencyRollCallEntry).filter(EmergencyRollCallEntry.emergency_event_id == event_id).all()
    count = 0
    for entry in entries:
        entry.snapshot_visitor_name = ANONYMIZED_NAME
        entry.snapshot_company = None
        entry.snapshot_mobile = None
        entry.snapshot_registration_reference = None
        entry.snapshot_badge_number = None
        count += 1
    if count:
        AuditService(db).record(
            action="EMERGENCY_SNAPSHOT_ANONYMIZED",
            entity_type="emergency_event",
            entity_id=str(event_id),
            actor_id=actor.user_id if actor else None,
            actor_email=actor.email if actor else None,
            after_value={"entries": count},
        )
    return count


def preview_policy(db: Session, ctx: AuthContext, policy_id: int) -> Dict[str, Any]:
    _require_read(ctx)
    policy = db.query(DataRetentionPolicy).filter(DataRetentionPolicy.id == policy_id).first()
    if not policy or not policy.is_active:
        raise RetentionError("not_found", "Retention policy not found.", 404)
    eligible, skipped = _count_eligible(db, policy)
    AuditService(db).record(
        action="RETENTION_PREVIEW_GENERATED",
        entity_type="data_retention_policy",
        entity_id=str(policy_id),
        actor_id=ctx.user_id,
        actor_email=ctx.email,
        after_value={"eligible": len(eligible), "skipped": len(skipped)},
    )
    return {
        "policy": _policy_dict(policy, db),
        "eligible_count": len(eligible),
        "skipped_count": len(skipped),
        "eligible_ids_sample": eligible[:20],
    }


def _count_eligible(db: Session, policy: DataRetentionPolicy) -> Tuple[List[int], List[int]]:
    cutoff = _cutoff(policy.retention_days)
    category = policy.data_category
    if category == "VISITOR_PII":
        return _eligible_visitor_pii(db, policy)
    if category == "NOTIFICATION_CONTENT":
        rows = db.query(Notification.id).filter(Notification.created_at < cutoff).all()
        return [r[0] for r in rows], []
    if category == "AI_INTERACTION":
        rows = db.query(AIInteraction.id).filter(AIInteraction.created_at < cutoff).all()
        return [r[0] for r in rows], []
    if category == "VISIT_FREE_TEXT":
        rows = db.query(Visit.id).filter(Visit.updated_at < cutoff).all()
        eligible = []
        skipped = []
        for (vid,) in rows:
            visit = db.query(Visit).filter(Visit.id == vid).first()
            if visit and _visitor_retention_blocked(db, visit.visitor_id):
                skipped.append(vid)
            else:
                eligible.append(vid)
        return eligible, skipped
    if category == "COMPLIANCE_DOCUMENT_FILE":
        rows = (
            db.query(ComplianceDocument.id)
            .filter(
                ComplianceDocument.uploaded_at < cutoff,
                ComplianceDocument.storage_state != "PURGED",
                ComplianceDocument.status.in_(["EXPIRED", "REJECTED"]),
            )
            .all()
        )
        return [r[0] for r in rows], []
    if category == "EMERGENCY_SNAPSHOT_PII":
        rows = (
            db.query(EmergencyEvent.id)
            .filter(EmergencyEvent.status == "CLOSED", EmergencyEvent.closed_at.isnot(None), EmergencyEvent.closed_at < cutoff)
            .all()
        )
        return [r[0] for r in rows], []
    return [], []


def execute_policy(db: Session, ctx: AuthContext, policy_id: int) -> Dict[str, Any]:
    _require_execute(ctx)
    return _execute_policy(db, policy_id, ctx)


def execute_policy_scheduled(db: Session, policy_id: int) -> Dict[str, Any]:
    """Run retention without a user context (automated scheduler only)."""
    return _execute_policy(db, policy_id, None)


def _execute_policy(db: Session, policy_id: int, ctx: Optional[AuthContext]) -> Dict[str, Any]:
    policy = db.query(DataRetentionPolicy).filter(DataRetentionPolicy.id == policy_id).first()
    if not policy or not policy.is_active:
        raise RetentionError("not_found", "Retention policy not found.", 404)
    run = DataRetentionRun(
        policy_id=policy_id,
        mode="EXECUTE",
        status="RUNNING",
        started_by_user_id=ctx.user_id if ctx else None,
    )
    db.add(run)
    db.flush()
    actor_id = ctx.user_id if ctx else None
    actor_email = ctx.email if ctx else None
    AuditService(db).record(
        action="RETENTION_RUN_STARTED",
        entity_type="data_retention_run",
        entity_id=str(run.id),
        actor_id=actor_id,
        actor_email=actor_email,
    )
    eligible, skipped_ids = _count_eligible(db, policy)
    run.eligible_count = len(eligible)
    run.skipped_count = len(skipped_ids)
    processed = 0
    failed = 0
    for item_id in eligible:
        try:
            ok = _process_item(db, policy, item_id, ctx)
            if ok:
                processed += 1
            else:
                run.skipped_count += 1
        except Exception:
            failed += 1
    run.processed_count = processed
    run.failed_count = failed
    run.status = "FAILED" if failed and not processed else "COMPLETED"
    run.completed_at = datetime.now(timezone.utc)
    AuditService(db).record(
        action="RETENTION_RUN_COMPLETED" if run.status == "COMPLETED" else "RETENTION_RUN_FAILED",
        entity_type="data_retention_run",
        entity_id=str(run.id),
        actor_id=actor_id,
        actor_email=actor_email,
        after_value={"processed": processed, "failed": failed},
    )
    return {
        "run_id": run.id,
        "status": run.status,
        "eligible_count": run.eligible_count,
        "processed_count": run.processed_count,
        "skipped_count": run.skipped_count,
        "failed_count": run.failed_count,
    }


def _process_item(db: Session, policy: DataRetentionPolicy, item_id: int, ctx: AuthContext) -> bool:
    cat = policy.data_category
    if cat == "VISITOR_PII":
        return _anonymize_visitor(db, item_id, ctx)
    if cat == "VISIT_FREE_TEXT":
        return _purge_visit_free_text(db, item_id)
    if cat == "NOTIFICATION_CONTENT":
        return _purge_notification(db, item_id)
    if cat == "AI_INTERACTION":
        return _purge_ai_interaction(db, item_id)
    if cat == "COMPLIANCE_DOCUMENT_FILE":
        return _purge_compliance_file(db, item_id, ctx)
    if cat == "EMERGENCY_SNAPSHOT_PII":
        return _anonymize_emergency_snapshot(db, item_id, ctx) > 0
    return False


def seed_default_retention_policies(db: Session) -> None:
    defaults = [
        ("VISITOR_PII", 365, "ANONYMIZE"),
        ("VISIT_FREE_TEXT", 365, "PURGE_CONTENT"),
        ("NOTIFICATION_CONTENT", 90, "PURGE_CONTENT"),
        ("AI_INTERACTION", 30, "PURGE_CONTENT"),
        ("EMERGENCY_SNAPSHOT_PII", 365, "ANONYMIZE"),
    ]
    for category, days, action in defaults:
        exists = (
            db.query(DataRetentionPolicy)
            .filter(DataRetentionPolicy.data_category == category, DataRetentionPolicy.scope_type == "GLOBAL")
            .first()
        )
        if not exists:
            db.add(
                DataRetentionPolicy(
                    data_category=category,
                    scope_type="GLOBAL",
                    retention_days=days,
                    action=action,
                    is_active=True,
                )
            )
