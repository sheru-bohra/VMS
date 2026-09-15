"""Physical access credential provisioning and lifecycle."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session, joinedload

from app.application.access_attention_service import list_attention_items
from app.application.access_control_provider import (
    AccessCredentialRequest,
    get_access_control_provider,
)
from app.application.audit_service import AuditService
from app.application.auth_service import AuthContext
from app.application.site_scope_service import can_access_location
from app.core.config import settings
from app.core.provider_error_sanitizer import redact_sensitive_text, sanitize_access_provider_error
from app.domain.enums import PhysicalAccessStatus, Permission, VisitStatus, role_has_permission
from app.domain.models import (
    AccessProfile,
    AccessProvisioningAttempt,
    LocationAccessConfiguration,
    Visit,
    Visitor,
    VisitorAccessCredential,
    VisitorTypeAccessProfile,
)


class AccessProvisioningError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


ATTEMPT_PENDING = "PENDING"
ATTEMPT_PROCESSING = "PROCESSING"
ATTEMPT_COMPLETED = "COMPLETED"
ATTEMPT_FAILED = "FAILED"

ACTION_PROVISION = "PROVISION"
ACTION_REVOKE = "REVOKE"
ACTION_STATUS_SYNC = "STATUS_SYNC"

logger = logging.getLogger(__name__)


def _require_read(ctx: AuthContext) -> None:
    if not role_has_permission(ctx.role, Permission.ACCESS_READ):
        raise AccessProvisioningError("forbidden", "Permission denied.", 403)


def _require_operate(ctx: AuthContext) -> None:
    if not role_has_permission(ctx.role, Permission.ACCESS_OPERATE):
        raise AccessProvisioningError("forbidden", "Permission denied.", 403)


def _require_retry(ctx: AuthContext) -> None:
    if not role_has_permission(ctx.role, Permission.ACCESS_RETRY):
        raise AccessProvisioningError("forbidden", "Permission denied.", 403)


def _require_revoke(ctx: AuthContext) -> None:
    if not role_has_permission(ctx.role, Permission.ACCESS_REVOKE):
        raise AccessProvisioningError("forbidden", "Permission denied.", 403)


def _require_site(ctx: AuthContext, location_id: int) -> None:
    if not can_access_location(ctx, location_id):
        raise AccessProvisioningError("forbidden", "Location access denied.", 403)


def get_location_access_config(db: Session, location_id: int) -> Optional[LocationAccessConfiguration]:
    return (
        db.query(LocationAccessConfiguration)
        .filter(LocationAccessConfiguration.location_id == location_id)
        .first()
    )


def _is_access_enabled_at_location(db: Session, location_id: int) -> bool:
    if not settings.access_control_enabled:
        return False
    cfg = get_location_access_config(db, location_id)
    return bool(cfg and cfg.is_active and cfg.access_control_enabled)


def _resolve_access_profile(
    db: Session, location_id: int, visitor_type_id: Optional[int], location_cfg: LocationAccessConfiguration,
) -> Optional[AccessProfile]:
    if visitor_type_id:
        mapping = (
            db.query(VisitorTypeAccessProfile)
            .filter(
                VisitorTypeAccessProfile.location_id == location_id,
                VisitorTypeAccessProfile.visitor_type_id == visitor_type_id,
                VisitorTypeAccessProfile.is_active.is_(True),
            )
            .first()
        )
        if mapping:
            profile = db.query(AccessProfile).filter(
                AccessProfile.id == mapping.access_profile_id,
                AccessProfile.is_active.is_(True),
            ).first()
            if profile:
                return profile
    if location_cfg.default_access_profile_id:
        return db.query(AccessProfile).filter(
            AccessProfile.id == location_cfg.default_access_profile_id,
            AccessProfile.is_active.is_(True),
        ).first()
    return None


def calculate_valid_until(
    visit: Visit,
    checked_in_at: datetime,
    location_cfg: LocationAccessConfiguration,
) -> datetime:
    grace = timedelta(minutes=location_cfg.credential_grace_minutes)
    max_dur = timedelta(minutes=location_cfg.max_credential_duration_minutes)
    max_end = checked_in_at + max_dur

    candidate: Optional[datetime] = None
    if visit.scheduled_end:
        end = visit.scheduled_end
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        candidate = end + grace
    elif visit.expected_duration_minutes:
        candidate = checked_in_at + timedelta(minutes=visit.expected_duration_minutes) + grace
    else:
        candidate = checked_in_at + timedelta(hours=4) + grace

    return min(candidate, max_end)


def _existing_credential_for_visit(db: Session, visit_id: int) -> Optional[VisitorAccessCredential]:
    return (
        db.query(VisitorAccessCredential)
        .filter(VisitorAccessCredential.visit_id == visit_id)
        .order_by(VisitorAccessCredential.id.desc())
        .first()
    )


def request_access_on_checkin(
    db: Session,
    visit_id: int,
    actor_id: Optional[int] = None,
    actor_email: Optional[str] = None,
) -> None:
    visit = (
        db.query(Visit)
        .options(joinedload(Visit.visitor).joinedload(Visitor.visitor_type))
        .filter(Visit.id == visit_id)
        .first()
    )
    if not visit or visit.status != VisitStatus.ONSITE.value:
        return

    existing = _existing_credential_for_visit(db, visit_id)
    if existing and existing.status in (
        PhysicalAccessStatus.PENDING.value,
        PhysicalAccessStatus.ACTIVE.value,
        PhysicalAccessStatus.FAILED.value,
        PhysicalAccessStatus.MANUAL_ACTION_REQUIRED.value,
    ):
        return

    if not _is_access_enabled_at_location(db, visit.location_id):
        return

    location_cfg = get_location_access_config(db, visit.location_id)
    if not location_cfg:
        return

    visitor_type_id = visit.visitor.visitor_type_id if visit.visitor else None
    profile = _resolve_access_profile(db, visit.location_id, visitor_type_id, location_cfg)

    checked_in = visit.checked_in_at or datetime.now(timezone.utc)
    if checked_in.tzinfo is None:
        checked_in = checked_in.replace(tzinfo=timezone.utc)

    provider_key = location_cfg.provider_key or settings.access_control_provider
    status = PhysicalAccessStatus.PENDING.value
    last_error = None
    profile_id = profile.id if profile else None

    if not profile:
        status = PhysicalAccessStatus.MANUAL_ACTION_REQUIRED.value
        last_error = "NO_ACCESS_PROFILE_MAPPING"

    valid_until = calculate_valid_until(visit, checked_in, location_cfg)

    credential = VisitorAccessCredential(
        visit_id=visit_id,
        visitor_id=visit.visitor_id,
        location_id=visit.location_id,
        access_profile_id=profile_id,
        status=status,
        valid_from=checked_in,
        valid_until=valid_until,
        provider_key=provider_key,
        last_error_code=last_error,
    )
    db.add(credential)
    db.flush()

    AuditService(db).record(
        action="ACCESS_PROVISION_REQUESTED",
        entity_type="visitor_access_credential",
        entity_id=str(credential.id),
        actor_id=actor_id,
        actor_email=actor_email,
        location_id=visit.location_id,
        after_value={"visit_id": visit_id, "status": status},
    )

    if status == PhysicalAccessStatus.PENDING.value:
        _queue_attempt(db, credential.id, ACTION_PROVISION, f"PROVISION:{visit_id}")


def request_access_revoke_on_checkout(
    db: Session,
    visit_id: int,
    actor_id: Optional[int] = None,
    actor_email: Optional[str] = None,
) -> None:
    credentials = (
        db.query(VisitorAccessCredential)
        .filter(
            VisitorAccessCredential.visit_id == visit_id,
            VisitorAccessCredential.status.in_([
                PhysicalAccessStatus.ACTIVE.value,
                PhysicalAccessStatus.PENDING.value,
                PhysicalAccessStatus.FAILED.value,
                PhysicalAccessStatus.MANUAL_ACTION_REQUIRED.value,
            ]),
        )
        .all()
    )
    for cred in credentials:
        cred.status = PhysicalAccessStatus.REVOCATION_PENDING.value
        AuditService(db).record(
            action="ACCESS_REVOKE_REQUESTED",
            entity_type="visitor_access_credential",
            entity_id=str(cred.id),
            actor_id=actor_id,
            actor_email=actor_email,
            location_id=cred.location_id,
        )
        _queue_attempt(db, cred.id, ACTION_REVOKE, f"REVOKE:{cred.id}:{visit_id}")


def _queue_attempt(db: Session, credential_id: int, action: str, dedupe_key: str) -> None:
    exists = db.query(AccessProvisioningAttempt).filter(AccessProvisioningAttempt.dedupe_key == dedupe_key).first()
    if exists:
        return
    pending = (
        db.query(AccessProvisioningAttempt)
        .filter(
            AccessProvisioningAttempt.access_credential_id == credential_id,
            AccessProvisioningAttempt.action == action,
            AccessProvisioningAttempt.status == ATTEMPT_PENDING,
        )
        .first()
    )
    if pending:
        return
    db.add(
        AccessProvisioningAttempt(
            access_credential_id=credential_id,
            action=action,
            status=ATTEMPT_PENDING,
            attempt_number=1,
            dedupe_key=dedupe_key,
            available_at=datetime.now(timezone.utc),
        )
    )
    db.flush()


def process_pending_access_attempts(db: Session, limit: int = 50) -> int:
    now = datetime.now(timezone.utc)
    attempts = (
        db.query(AccessProvisioningAttempt)
        .filter(
            AccessProvisioningAttempt.status == ATTEMPT_PENDING,
            AccessProvisioningAttempt.available_at <= now,
        )
        .order_by(AccessProvisioningAttempt.id.asc())
        .limit(limit)
        .all()
    )
    processed = 0
    for attempt in attempts:
        try:
            attempt.status = ATTEMPT_PROCESSING
            attempt.started_at = now
            db.flush()
            if attempt.action == ACTION_PROVISION:
                _process_provision_attempt(db, attempt)
            elif attempt.action == ACTION_REVOKE:
                _process_revoke_attempt(db, attempt)
            attempt.completed_at = datetime.now(timezone.utc)
            attempt.status = ATTEMPT_COMPLETED
            processed += 1
        except Exception:
            attempt.status = ATTEMPT_FAILED
            attempt.error_code = "PROCESSING_ERROR"
            attempt.completed_at = datetime.now(timezone.utc)
        db.flush()
    return processed


def _process_provision_attempt(db: Session, attempt: AccessProvisioningAttempt) -> None:
    cred = db.query(VisitorAccessCredential).filter(VisitorAccessCredential.id == attempt.access_credential_id).first()
    if not cred or cred.status != PhysicalAccessStatus.PENDING.value:
        return

    profile = None
    if cred.access_profile_id:
        profile = db.query(AccessProfile).filter(AccessProfile.id == cred.access_profile_id).first()
    if not profile or not profile.is_active:
        cred.status = PhysicalAccessStatus.MANUAL_ACTION_REQUIRED.value
        cred.last_error_code = "NO_ACCESS_PROFILE" if not profile else "PROFILE_DEACTIVATED"
        AuditService(db).record(
            action="ACCESS_MANUAL_ACTION_REQUIRED",
            entity_type="visitor_access_credential",
            entity_id=str(cred.id),
            location_id=cred.location_id,
        )
        return

    provider = get_access_control_provider(cred.provider_key)
    caps = provider.capabilities()
    if not caps.get("supports_timed_access"):
        cred.status = PhysicalAccessStatus.MANUAL_ACTION_REQUIRED.value
        cred.last_error_code = "PROVIDER_NO_TIMED_ACCESS"
        return

    visit = db.query(Visit).options(joinedload(Visit.visitor)).filter(Visit.id == cred.visit_id).first()
    visitor_name = visit.visitor.full_name if visit and visit.visitor else "Visitor"
    visitor_type_name = None
    if visit and visit.visitor and visit.visitor.visitor_type:
        visitor_type_name = visit.visitor.visitor_type.name

    request = AccessCredentialRequest(
        credential_id=cred.id,
        visit_id=cred.visit_id,
        location_id=cred.location_id,
        access_profile_external_ref=profile.provider_external_profile_ref,
        visitor_display_name=visitor_name,
        visitor_type_name=visitor_type_name,
        valid_from=cred.valid_from or datetime.now(timezone.utc),
        valid_until=cred.valid_until or datetime.now(timezone.utc),
        idempotency_key=f"vms-access-{cred.id}",
    )
    result = provider.provision_access(request)
    if result.success:
        cred.status = PhysicalAccessStatus.ACTIVE.value
        cred.provider_credential_reference = result.provider_credential_reference
        cred.provisioned_at = datetime.now(timezone.utc)
        cred.last_error_code = None
        AuditService(db).record(
            action="ACCESS_PROVISIONED",
            entity_type="visitor_access_credential",
            entity_id=str(cred.id),
            location_id=cred.location_id,
            after_value={"provider_ref": result.provider_credential_reference},
        )
    else:
        safe_code = sanitize_access_provider_error(result.error_code)
        cred.last_error_code = safe_code
        logger.warning(
            "Access provision failed credential=%s visit=%s error=%s",
            cred.id,
            cred.visit_id,
            redact_sensitive_text(str(result.error_code or safe_code)),
        )
        if result.transient and attempt.attempt_number < settings.access_provider_max_attempts:
            cred.status = PhysicalAccessStatus.PENDING.value
            _schedule_retry(db, cred, attempt, ACTION_PROVISION)
        else:
            cred.status = (
                PhysicalAccessStatus.MANUAL_ACTION_REQUIRED.value
                if not result.transient
                else PhysicalAccessStatus.FAILED.value
            )
            AuditService(db).record(
                action="ACCESS_PROVISION_FAILED",
                entity_type="visitor_access_credential",
                entity_id=str(cred.id),
                location_id=cred.location_id,
                after_value={"error_code": safe_code},
            )


def _process_revoke_attempt(db: Session, attempt: AccessProvisioningAttempt) -> None:
    cred = db.query(VisitorAccessCredential).filter(VisitorAccessCredential.id == attempt.access_credential_id).first()
    if not cred or cred.status != PhysicalAccessStatus.REVOCATION_PENDING.value:
        return
    if not cred.provider_credential_reference:
        cred.status = PhysicalAccessStatus.REVOKED.value
        cred.revoked_at = datetime.now(timezone.utc)
        return

    provider = get_access_control_provider(cred.provider_key)
    result = provider.revoke_access(cred.provider_credential_reference)
    if result.success:
        cred.status = PhysicalAccessStatus.REVOKED.value
        cred.revoked_at = datetime.now(timezone.utc)
        cred.last_error_code = None
        if cred.expired_at or (cred.valid_until and cred.valid_until < datetime.now(timezone.utc)):
            cred.expired_at = cred.expired_at or datetime.now(timezone.utc)
            AuditService(db).record(
                action="ACCESS_EXPIRED",
                entity_type="visitor_access_credential",
                entity_id=str(cred.id),
                location_id=cred.location_id,
            )
        AuditService(db).record(
            action="ACCESS_REVOKED",
            entity_type="visitor_access_credential",
            entity_id=str(cred.id),
            location_id=cred.location_id,
        )
    else:
        safe_code = sanitize_access_provider_error(result.error_code)
        cred.last_error_code = safe_code
        logger.warning(
            "Access revoke failed credential=%s visit=%s error=%s",
            cred.id,
            cred.visit_id,
            redact_sensitive_text(str(result.error_code or safe_code)),
        )
        if result.transient and attempt.attempt_number < settings.access_provider_max_attempts:
            _schedule_retry(db, cred, attempt, ACTION_REVOKE)
        else:
            cred.status = PhysicalAccessStatus.MANUAL_ACTION_REQUIRED.value
            AuditService(db).record(
                action="ACCESS_REVOKE_FAILED",
                entity_type="visitor_access_credential",
                entity_id=str(cred.id),
                location_id=cred.location_id,
                after_value={"error_code": safe_code},
            )


def _schedule_retry(
    db: Session,
    cred: VisitorAccessCredential,
    attempt: AccessProvisioningAttempt,
    action: str,
) -> None:
    delay = settings.access_provider_retry_base_seconds * attempt.attempt_number
    dedupe = f"{action}:{cred.id}:retry:{attempt.attempt_number + 1}"
    _queue_attempt(db, cred.id, action, dedupe)
    pending = (
        db.query(AccessProvisioningAttempt)
        .filter(AccessProvisioningAttempt.dedupe_key == dedupe)
        .first()
    )
    if pending:
        delay = settings.access_provider_retry_base_seconds * attempt.attempt_number
        pending.available_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
        pending.attempt_number = attempt.attempt_number + 1


def reconcile_checked_out_active_credentials(db: Session) -> int:
    """Queue revocation for checked-out visits that still have ACTIVE credentials."""
    rows = (
        db.query(VisitorAccessCredential)
        .filter(VisitorAccessCredential.status == PhysicalAccessStatus.ACTIVE.value)
        .all()
    )
    count = 0
    for cred in rows:
        visit = db.query(Visit).filter(Visit.id == cred.visit_id).first()
        if not visit or visit.status != VisitStatus.CHECKED_OUT.value:
            continue
        cred.status = PhysicalAccessStatus.REVOCATION_PENDING.value
        _queue_attempt(db, cred.id, ACTION_REVOKE, f"RECONCILE:{cred.id}")
        count += 1
    return count


def process_expired_credentials(db: Session) -> int:
    now = datetime.now(timezone.utc)
    expired = (
        db.query(VisitorAccessCredential)
        .filter(
            VisitorAccessCredential.status == PhysicalAccessStatus.ACTIVE.value,
            VisitorAccessCredential.valid_until.isnot(None),
        )
        .all()
    )
    count = 0
    for cred in expired:
        until = cred.valid_until
        if until and until.tzinfo is None:
            until = until.replace(tzinfo=timezone.utc)
        if until is None or until >= now:
            continue
        cred.status = PhysicalAccessStatus.REVOCATION_PENDING.value
        _queue_attempt(db, cred.id, ACTION_REVOKE, f"EXPIRE:{cred.id}")
        count += 1
    return count


def _credential_dict(db: Session, cred: VisitorAccessCredential) -> Dict[str, Any]:
    visit = db.query(Visit).options(joinedload(Visit.visitor), joinedload(Visit.location)).filter(Visit.id == cred.visit_id).first()
    profile_name = None
    if cred.access_profile_id:
        p = db.query(AccessProfile).filter(AccessProfile.id == cred.access_profile_id).first()
        profile_name = p.name if p else None
    visitor_name = visit.visitor.full_name if visit and visit.visitor else ""
    location_name = visit.location.name if visit and visit.location else ""
    return {
        "id": cred.id,
        "visit_id": cred.visit_id,
        "visitor_id": cred.visitor_id,
        "location_id": cred.location_id,
        "location_name": location_name,
        "visitor_name": visitor_name,
        "access_profile_id": cred.access_profile_id,
        "access_profile_name": profile_name,
        "status": cred.status,
        "valid_from": cred.valid_from.isoformat() if cred.valid_from else None,
        "valid_until": cred.valid_until.isoformat() if cred.valid_until else None,
        "provider_key": cred.provider_key,
        "last_error_code": cred.last_error_code,
        "provisioned_at": cred.provisioned_at.isoformat() if cred.provisioned_at else None,
        "revoked_at": cred.revoked_at.isoformat() if cred.revoked_at else None,
        "visit_status": visit.status if visit else None,
        "checked_out_at": visit.checked_out_at.isoformat() if visit and visit.checked_out_at else None,
    }


def list_credentials(
    db: Session,
    ctx: AuthContext,
    status_filter: Optional[str] = None,
    attention_only: bool = False,
) -> List[Dict[str, Any]]:
    _require_read(ctx)
    if attention_only:
        items = list_attention_items(db, ctx)
        cred_ids = {i["credential_id"] for i in items if i.get("credential_id")}
        if not cred_ids:
            return []
        rows = db.query(VisitorAccessCredential).filter(VisitorAccessCredential.id.in_(cred_ids)).all()
        result = []
        for cred in rows:
            row = _credential_dict(db, cred)
            match = next((i for i in items if i.get("credential_id") == cred.id), None)
            if match:
                row["severity"] = match.get("severity")
                row["reason_code"] = match.get("reason_code")
                row["attention_title"] = match.get("title")
                row["attention_message"] = match.get("message")
                row["recommended_action"] = match.get("recommended_action")
            result.append(row)
        severity_rank = {"URGENT": 0, "ATTENTION": 1, "INFORMATION": 2}
        result.sort(key=lambda x: severity_rank.get(x.get("severity", "INFORMATION"), 9))
        return result

    q = db.query(VisitorAccessCredential).order_by(VisitorAccessCredential.updated_at.desc())
    if status_filter:
        q = q.filter(VisitorAccessCredential.status == status_filter)
    else:
        q = q.filter(VisitorAccessCredential.status == PhysicalAccessStatus.ACTIVE.value)

    rows = q.limit(200).all()
    result = []
    for cred in rows:
        if not can_access_location(ctx, cred.location_id):
            continue
        result.append(_credential_dict(db, cred))
    return result


def get_credential(db: Session, ctx: AuthContext, credential_id: int) -> Dict[str, Any]:
    _require_read(ctx)
    cred = db.query(VisitorAccessCredential).filter(VisitorAccessCredential.id == credential_id).first()
    if not cred:
        raise AccessProvisioningError("not_found", "Credential not found.", 404)
    _require_site(ctx, cred.location_id)
    return _credential_dict(db, cred)


def _accelerate_pending_attempt(db: Session, credential_id: int, action: str) -> None:
    pending = (
        db.query(AccessProvisioningAttempt)
        .filter(
            AccessProvisioningAttempt.access_credential_id == credential_id,
            AccessProvisioningAttempt.action == action,
            AccessProvisioningAttempt.status == ATTEMPT_PENDING,
        )
        .order_by(AccessProvisioningAttempt.id.desc())
        .first()
    )
    if pending:
        pending.available_at = datetime.now(timezone.utc)


def retry_credential(db: Session, ctx: AuthContext, credential_id: int) -> Dict[str, Any]:
    _require_retry(ctx)
    cred = db.query(VisitorAccessCredential).filter(VisitorAccessCredential.id == credential_id).first()
    if not cred:
        raise AccessProvisioningError("not_found", "Credential not found.", 404)
    _require_site(ctx, cred.location_id)

    if cred.status in (PhysicalAccessStatus.FAILED.value, PhysicalAccessStatus.MANUAL_ACTION_REQUIRED.value):
        cred.status = PhysicalAccessStatus.PENDING.value
        _queue_attempt(db, cred.id, ACTION_PROVISION, f"RETRY-PROVISION:{cred.id}")
        _accelerate_pending_attempt(db, cred.id, ACTION_PROVISION)
    elif cred.status == PhysicalAccessStatus.REVOCATION_PENDING.value:
        _queue_attempt(db, cred.id, ACTION_REVOKE, f"RETRY-REVOKE:{cred.id}")
        _accelerate_pending_attempt(db, cred.id, ACTION_REVOKE)
    elif cred.status == PhysicalAccessStatus.PENDING.value and cred.last_error_code:
        _accelerate_pending_attempt(db, cred.id, ACTION_PROVISION)
        _queue_attempt(db, cred.id, ACTION_PROVISION, f"RETRY-PROVISION:{cred.id}")
        _accelerate_pending_attempt(db, cred.id, ACTION_PROVISION)
    else:
        raise AccessProvisioningError("invalid_state", "Credential is not in a retryable state.", 409)

    db.flush()
    process_pending_access_attempts(db, limit=5)
    db.refresh(cred)
    return _credential_dict(db, cred)


def revoke_credential_manual(db: Session, ctx: AuthContext, credential_id: int) -> Dict[str, Any]:
    _require_revoke(ctx)
    cred = db.query(VisitorAccessCredential).filter(VisitorAccessCredential.id == credential_id).first()
    if not cred:
        raise AccessProvisioningError("not_found", "Credential not found.", 404)
    _require_site(ctx, cred.location_id)
    if cred.status not in (PhysicalAccessStatus.ACTIVE.value, PhysicalAccessStatus.PENDING.value):
        raise AccessProvisioningError("invalid_state", "Credential cannot be revoked in current state.", 409)

    cred.status = PhysicalAccessStatus.REVOCATION_PENDING.value
    AuditService(db).record(
        action="ACCESS_REVOKE_REQUESTED",
        entity_type="visitor_access_credential",
        entity_id=str(cred.id),
        actor_id=ctx.user_id,
        actor_email=ctx.email,
        location_id=cred.location_id,
        metadata={"manual": True},
    )
    _queue_attempt(db, cred.id, ACTION_REVOKE, f"MANUAL-REVOKE:{cred.id}:{datetime.now(timezone.utc).isoformat()}")
    db.flush()
    process_pending_access_attempts(db, limit=5)
    db.refresh(cred)
    return _credential_dict(db, cred)
