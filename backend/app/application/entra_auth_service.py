"""Resolve Entra-authenticated users to VMS principals (authorization in VMS)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.application.audit_service import AuditService
from app.application.auth_service import AuthContext, _build_context
from app.application.vms_native_auth_service import is_vms_native_provider
from app.core.config import settings
from app.domain.enums import AdminRole
from app.domain.models import AdminUser


class EntraAuthError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 403):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


_UNAUTHORIZED_MSG = (
    "Your Microsoft account was successfully authenticated, but you do not currently have access "
    "to the Visitor Management System. Please contact the VMS administrator."
)
_DISABLED_MSG = "Your VMS access has been disabled. Please contact the VMS administrator."


def _normalize_email(claims: Dict[str, Any]) -> Optional[str]:
    email = claims.get("preferred_username") or claims.get("upn") or claims.get("email")
    if not email:
        return None
    return email.strip().lower()


def _count_active_global_admins(db: Session) -> int:
    return (
        db.query(AdminUser)
        .filter(AdminUser.role == AdminRole.GLOBAL_ADMIN.value, AdminUser.is_active.is_(True))
        .count()
    )


def _try_bootstrap_global_admin(
    db: Session,
    claims: Dict[str, Any],
    email: str,
    tid: str,
    oid: str,
) -> Optional[AdminUser]:
    """Create the first Global Admin when no global admin exists and bootstrap email matches."""
    bootstrap_email = (settings.vms_bootstrap_admin_email or "").strip().lower()
    if not bootstrap_email or email != bootstrap_email:
        return None
    if _count_active_global_admins(db) > 0:
        return None

    now = datetime.now(timezone.utc)
    display_name = (claims.get("name") or email).strip()
    user = AdminUser(
        email=email,
        display_name=display_name,
        role=AdminRole.GLOBAL_ADMIN.value,
        is_owner=True,
        is_active=True,
        entra_tenant_id=tid,
        entra_object_id=oid,
        auth_provider="entra",
        identity_linked_at=now,
        last_login_at=now,
    )
    db.add(user)
    db.flush()

    AuditService(db).record(
        action="ENTRA_IDENTITY_BOUND",
        entity_type="admin_user",
        entity_id=str(user.id),
        actor_id=user.id,
        actor_email=user.email,
        metadata={"entra_oid": oid, "tenant_id": tid, "bootstrap": True},
    )
    AuditService(db).record(
        action="USER_CREATED",
        entity_type="admin_user",
        entity_id=str(user.id),
        actor_id=user.id,
        actor_email=user.email,
        after_value={"email": email, "role": AdminRole.GLOBAL_ADMIN.value, "bootstrap": True},
    )
    return user


def resolve_entra_user(db: Session, claims: Dict[str, Any]) -> AuthContext:
    tid = claims.get("tid")
    oid = claims.get("oid")
    if not tid or not oid:
        raise EntraAuthError("AUTH_TOKEN_INVALID", "Token missing required identity claims.", 401)

    user = (
        db.query(AdminUser)
        .filter(AdminUser.entra_tenant_id == tid, AdminUser.entra_object_id == oid)
        .first()
    )

    if not user:
        email = _normalize_email(claims)
        if email:
            candidates = (
                db.query(AdminUser)
                .filter(AdminUser.email.ilike(email), AdminUser.is_active.is_(True))
                .all()
            )
            if len(candidates) == 1:
                user = candidates[0]
                if is_vms_native_provider(user.auth_provider):
                    raise EntraAuthError("VMS_USER_NOT_AUTHORIZED", _UNAUTHORIZED_MSG)
                if user.entra_object_id and user.entra_object_id != oid:
                    AuditService(db).record(
                        action="ENTRA_IDENTITY_REBIND_ATTEMPT",
                        entity_type="admin_user",
                        entity_id=str(user.id),
                        actor_email=user.email,
                        metadata={"attempted_oid": oid, "bound_oid": user.entra_object_id},
                    )
                    raise EntraAuthError(
                        "IDENTITY_LINK_CONFLICT",
                        "This VMS account is linked to a different Microsoft identity.",
                        403,
                    )
                existing_oid = (
                    db.query(AdminUser)
                    .filter(AdminUser.entra_tenant_id == tid, AdminUser.entra_object_id == oid)
                    .first()
                )
                if existing_oid and existing_oid.id != user.id:
                    raise EntraAuthError(
                        "IDENTITY_LINK_CONFLICT",
                        "This Microsoft identity is linked to another VMS account.",
                        403,
                    )

                now = datetime.now(timezone.utc)
                user.entra_tenant_id = tid
                user.entra_object_id = oid
                user.auth_provider = "entra"
                user.identity_linked_at = now
                if claims.get("name"):
                    user.display_name = claims.get("name")
                AuditService(db).record(
                    action="ENTRA_IDENTITY_BOUND",
                    entity_type="admin_user",
                    entity_id=str(user.id),
                    actor_id=user.id,
                    actor_email=user.email,
                    metadata={"entra_oid": oid, "tenant_id": tid},
                )
                db.flush()

        if not user and email:
            user = _try_bootstrap_global_admin(db, claims, email, tid, oid)

    if not user:
        email = _normalize_email(claims)
        AuditService(db).record(
            action="UNAUTHORIZED_SSO_LOGIN",
            entity_type="admin_user",
            actor_email=email,
            metadata={"entra_oid": oid, "tenant_id": tid},
        )
        raise EntraAuthError("VMS_USER_NOT_AUTHORIZED", _UNAUTHORIZED_MSG)

    if not user.is_active:
        AuditService(db).record(
            action="SSO_LOGIN_FAILED",
            entity_type="admin_user",
            entity_id=str(user.id),
            actor_email=user.email,
            metadata={"reason": "disabled"},
        )
        raise EntraAuthError("VMS_USER_INACTIVE", _DISABLED_MSG)

    if is_vms_native_provider(user.auth_provider):
        AuditService(db).record(
            action="SSO_LOGIN_FAILED",
            entity_type="admin_user",
            entity_id=str(user.id),
            actor_email=user.email,
            metadata={"reason": "vms_native_only"},
        )
        raise EntraAuthError("VMS_USER_NOT_AUTHORIZED", _UNAUTHORIZED_MSG)

    user.last_login_at = datetime.now(timezone.utc)
    if claims.get("name") and not user.display_name:
        user.display_name = claims.get("name")
    if not user.auth_provider:
        user.auth_provider = "entra"
    db.flush()

    ctx = _build_context(user)
    ctx.auth_provider = user.auth_provider or "entra"
    AuditService(db).record(
        action="SSO_LOGIN_SUCCESS",
        entity_type="admin_user",
        entity_id=str(user.id),
        actor_id=user.id,
        actor_email=user.email,
        metadata={"auth_provider": "entra"},
    )
    return ctx
