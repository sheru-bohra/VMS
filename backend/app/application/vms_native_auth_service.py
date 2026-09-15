"""VMS native email + password authentication for all staff."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Request
from sqlalchemy.orm import Session

from app.application.audit_service import AuditService
from app.application.auth_service import AuthContext, _build_context
from app.application.password_service import hash_password, verify_password
from app.application.rate_limit_service import check_vms_native_login_rate_limit
from app.core.config import settings
from app.core.errors import APIError
from app.domain.models import AdminUser

VMS_NATIVE_AUTH_PROVIDER = "vms_native"
LEGACY_DIRECT_AUTH_PROVIDER = "direct"
VMS_NATIVE_TOKEN_ISSUER = "vms-native"
LEGACY_DIRECT_TOKEN_ISSUER = "vms-direct-owner"
_INVALID_CREDENTIALS_MSG = "Invalid email or password."
_logger = logging.getLogger(__name__)


class VmsNativeAuthError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 401):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def is_vms_native_provider(auth_provider: Optional[str]) -> bool:
    return auth_provider in (VMS_NATIVE_AUTH_PROVIDER, LEGACY_DIRECT_AUTH_PROVIDER)


def _session_secret() -> str:
    secret = settings.vms_data_encryption_key or settings.audit_integrity_key
    if not secret:
        raise RuntimeError("VMS_DATA_ENCRYPTION_KEY or AUDIT_INTEGRITY_KEY is required for VMS native sessions.")
    return secret


def is_vms_native_token(token: str) -> bool:
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        return payload.get("iss") in (VMS_NATIVE_TOKEN_ISSUER, LEGACY_DIRECT_TOKEN_ISSUER)
    except Exception:
        return False


def issue_vms_native_token(user: AdminUser) -> tuple[str, int]:
    ttl_seconds = settings.resolved_vms_native_session_ttl_minutes * 60
    now = datetime.now(timezone.utc)
    exp = now + timedelta(seconds=ttl_seconds)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "iss": VMS_NATIVE_TOKEN_ISSUER,
        "typ": "vms_native",
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    token = jwt.encode(payload, _session_secret(), algorithm="HS256")
    return token, ttl_seconds


def authenticate_vms_native_token(db: Session, token: str) -> AuthContext:
    try:
        payload = jwt.decode(
            token,
            _session_secret(),
            algorithms=["HS256"],
            options={"require": ["exp", "sub", "email", "iss"]},
        )
    except jwt.ExpiredSignatureError:
        raise VmsNativeAuthError("AUTH_TOKEN_EXPIRED", "Authentication required.", 401)
    except jwt.InvalidTokenError:
        raise VmsNativeAuthError("AUTH_TOKEN_INVALID", "Authentication required.", 401)

    if payload.get("iss") not in (VMS_NATIVE_TOKEN_ISSUER, LEGACY_DIRECT_TOKEN_ISSUER):
        raise VmsNativeAuthError("AUTH_TOKEN_INVALID", "Authentication required.", 401)

    user_id = int(payload["sub"])
    user = db.query(AdminUser).filter(AdminUser.id == user_id).first()
    if not user or not user.is_active:
        raise VmsNativeAuthError("AUTH_TOKEN_INVALID", "Authentication required.", 401)
    if not is_vms_native_provider(user.auth_provider):
        raise VmsNativeAuthError("AUTH_TOKEN_INVALID", "Authentication required.", 401)
    if user.email.lower() != str(payload.get("email", "")).lower():
        raise VmsNativeAuthError("AUTH_TOKEN_INVALID", "Authentication required.", 401)

    issued_at = payload.get("iat")
    if issued_at and user.direct_owner_sessions_valid_after:
        token_iat = datetime.fromtimestamp(issued_at, tz=timezone.utc)
        valid_after = user.direct_owner_sessions_valid_after
        if valid_after.tzinfo is None:
            valid_after = valid_after.replace(tzinfo=timezone.utc)
        if token_iat <= valid_after:
            raise VmsNativeAuthError("AUTH_TOKEN_INVALID", "Authentication required.", 401)

    ctx = _build_context(user)
    ctx.auth_provider = VMS_NATIVE_AUTH_PROVIDER
    return ctx


def _account_locked(user: AdminUser, now: datetime) -> bool:
    if not user.locked_until:
        return False
    locked_until = user.locked_until
    if locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=timezone.utc)
    return locked_until > now


def _record_failed_login(db: Session, user: Optional[AdminUser], email: str) -> None:
    AuditService(db).record(
        action="LOGIN_FAILURE",
        entity_type="auth",
        entity_id=str(user.id) if user else None,
        actor_email=email if user else None,
        metadata={"auth_provider": VMS_NATIVE_AUTH_PROVIDER},
    )
    if not user:
        return
    user.failed_login_count = (user.failed_login_count or 0) + 1
    if user.failed_login_count >= settings.resolved_vms_native_max_failed_attempts:
        user.locked_until = datetime.now(timezone.utc) + timedelta(
            minutes=settings.resolved_vms_native_lockout_minutes
        )


def _clear_login_failures(user: AdminUser) -> None:
    user.failed_login_count = 0
    user.locked_until = None


def authenticate_vms_native_login(
    db: Session,
    email: str,
    password: str,
    request: Request,
) -> tuple[str, int, bool]:
    if not settings.resolved_vms_native_auth_enabled:
        raise APIError(404, "not_found", "Not found.")

    normalized = email.strip().lower()
    check_vms_native_login_rate_limit(request, normalized)

    now = datetime.now(timezone.utc)
    user = db.query(AdminUser).filter(AdminUser.email.ilike(normalized)).first()

    def fail(reason: str) -> None:
        if not settings.is_production:
            _logger.debug("VMS native login rejected for %s: %s", normalized, reason)
        _record_failed_login(db, user if user and user.is_active else None, normalized)
        db.flush()
        raise APIError(401, "invalid_credentials", _INVALID_CREDENTIALS_MSG)

    if not user:
        fail("user_not_found")

    if not user.is_active:
        AuditService(db).record(
            action="ACCOUNT_DISABLED_LOGIN_ATTEMPT",
            entity_type="admin_user",
            entity_id=str(user.id),
            actor_email=normalized,
            metadata={"auth_provider": VMS_NATIVE_AUTH_PROVIDER},
        )
        fail("inactive_user")

    if not is_vms_native_provider(user.auth_provider):
        fail("provider_mismatch")

    if _account_locked(user, now):
        _record_failed_login(db, user, normalized)
        db.flush()
        if not settings.is_production:
            _logger.debug("VMS native login rejected for %s: account_locked", normalized)
        raise APIError(401, "invalid_credentials", _INVALID_CREDENTIALS_MSG)

    if not user.password_hash:
        fail("missing_password_hash")

    if not verify_password(user.password_hash, password):
        fail("password_verification_failed")

    _clear_login_failures(user)
    user.last_login_at = now
    db.flush()

    token, expires_in = issue_vms_native_token(user)
    AuditService(db).record(
        action="LOGIN_SUCCESS",
        entity_type="admin_user",
        entity_id=str(user.id),
        actor_id=user.id,
        actor_email=user.email,
        metadata={"auth_provider": VMS_NATIVE_AUTH_PROVIDER},
    )
    return token, expires_in, bool(user.force_password_change)


def invalidate_vms_native_sessions(user: AdminUser) -> None:
    user.direct_owner_sessions_valid_after = datetime.now(timezone.utc)


def _mark_owner_credential_established(user: AdminUser, when: Optional[datetime] = None) -> None:
    if not user.is_owner:
        return
    user.initial_credential_provisioned_at = when or datetime.now(timezone.utc)


def set_user_password(
    db: Session,
    user: AdminUser,
    new_password: str,
    *,
    clear_force_change: bool = True,
) -> None:
    from app.application.password_policy import validate_password_policy

    validate_password_policy(new_password)
    user.password_hash = hash_password(new_password)
    user.password_changed_at = datetime.now(timezone.utc)
    user.auth_provider = VMS_NATIVE_AUTH_PROVIDER
    _mark_owner_credential_established(user)
    if clear_force_change:
        user.force_password_change = False
    db.flush()


def _provision_bootstrap_password(user: AdminUser, raw_password: str) -> None:
    """Hash env/bootstrap credentials without policy validation; require change if weak."""
    from app.application.password_policy import password_meets_policy

    user.password_hash = hash_password(raw_password)
    user.password_changed_at = datetime.now(timezone.utc)
    user.auth_provider = VMS_NATIVE_AUTH_PROVIDER
    user.force_password_change = not password_meets_policy(raw_password)


def _owner_has_argon2_hash(owner: AdminUser) -> bool:
    return bool(owner.password_hash and owner.password_hash.startswith("$argon2"))


def provision_owner_password_if_needed(db: Session, owner: AdminUser) -> None:
    """Idempotently provision owner VMS_NATIVE credentials from env when needed."""
    initial = (settings.global_admin_initial_password or "").strip()
    now = datetime.now(timezone.utc)

    if not is_vms_native_provider(owner.auth_provider):
        owner.auth_provider = VMS_NATIVE_AUTH_PROVIDER

    if owner.initial_credential_provisioned_at is not None:
        return

    if (
        owner.password_hash
        and initial
        and _owner_has_argon2_hash(owner)
        and verify_password(owner.password_hash, initial)
    ):
        owner.initial_credential_provisioned_at = now
        owner.failed_login_count = 0
        owner.locked_until = None
        db.flush()
        return

    if not initial:
        if not owner.password_hash:
            owner.force_password_change = True
        db.flush()
        return

    _provision_bootstrap_password(owner, initial)
    owner.initial_credential_provisioned_at = now
    owner.failed_login_count = 0
    owner.locked_until = None
    db.flush()


def change_own_password(
    db: Session,
    user: AdminUser,
    current_password: str,
    new_password: str,
    confirm_password: str,
) -> None:
    from app.application.password_policy import validate_password_confirmation, validate_password_policy

    validate_password_policy(new_password)
    validate_password_confirmation(new_password, confirm_password)
    if not user.password_hash or not verify_password(user.password_hash, current_password):
        raise APIError(401, "invalid_credentials", "Current password is incorrect.")
    if verify_password(user.password_hash, new_password):
        raise APIError(400, "validation_error", "New password must differ from your current password.")
    set_user_password(db, user, new_password, clear_force_change=True)
    invalidate_vms_native_sessions(user)


def ensure_vms_native_auth(db: Session, user: AdminUser) -> None:
    user.auth_provider = VMS_NATIVE_AUTH_PROVIDER
    if user.is_owner:
        provision_owner_password_if_needed(db, user)
    elif not user.password_hash:
        user.force_password_change = True
    db.flush()
