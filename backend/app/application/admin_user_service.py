"""VMS admin user provisioning and lifecycle."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session, joinedload

from app.application.audit_service import AuditService
from app.application.auth_service import AuthContext
from app.application.bootstrap import OWNER_EMAIL
from app.application.password_policy import generate_temporary_password, validate_password_confirmation, validate_password_policy
from app.application.registration_service import normalize_email
from app.application.vms_native_auth_service import (
    VMS_NATIVE_AUTH_PROVIDER,
    invalidate_vms_native_sessions,
    set_user_password,
)
from app.core.errors import APIError
from app.domain.enums import AdminRole, Permission, role_has_permission
from app.domain.models import AdminUser, Location, UserLocationAssignment


class AdminUserError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _require_read(ctx: AuthContext) -> None:
    if not role_has_permission(ctx.role, Permission.ADMINS_READ):
        raise AdminUserError("forbidden", "You do not have permission to view admin users.", 403)


def _require_manage(ctx: AuthContext) -> None:
    if not role_has_permission(ctx.role, Permission.ADMINS_MANAGE):
        raise AdminUserError("forbidden", "You do not have permission to manage admin users.", 403)


def _validate_password(password: str) -> None:
    try:
        validate_password_policy(password)
    except APIError as exc:
        raise AdminUserError(exc.code, exc.message, exc.status_code)


def _validate_password_match(password: str, confirmation: str) -> None:
    try:
        validate_password_confirmation(password, confirmation)
    except APIError as exc:
        raise AdminUserError(exc.code, exc.message, exc.status_code)


def _entra_linked(user: AdminUser) -> bool:
    return bool(user.entra_tenant_id and user.entra_object_id)


def _sso_status(user: AdminUser) -> str:
    if user.entra_tenant_id and user.entra_object_id:
        return "linked"
    if user.entra_tenant_id or user.entra_object_id:
        return "identity_issue"
    return "not_linked"


def _require_privileged_role_assignment(ctx: AuthContext, role: str) -> None:
    if role in (AdminRole.GLOBAL_ADMIN.value, AdminRole.HEAD_ADMIN.value):
        if ctx.role != AdminRole.GLOBAL_ADMIN.value and not ctx.is_owner:
            raise AdminUserError(
                "forbidden",
                "Only Global Admin can assign Global Admin or Head Admin roles.",
                403,
            )


def _serialize_user(user: AdminUser) -> Dict[str, Any]:
    location_ids = [a.location_id for a in user.location_assignments]
    locations = []
    for a in user.location_assignments:
        if a.location:
            locations.append(
                {
                    "id": a.location.id,
                    "name": a.location.name,
                    "code": a.location.code,
                    "city": a.location.city,
                }
            )
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role,
        "is_owner": user.is_owner,
        "is_active": user.is_active,
        "location_ids": location_ids,
        "assigned_locations": locations,
        "entra_linked": _entra_linked(user),
        "auth_provider": user.auth_provider,
        "force_password_change": bool(user.force_password_change),
        "sso_status": _sso_status(user),
        "access_status": "active" if user.is_active else "disabled",
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
        "identity_linked_at": user.identity_linked_at.isoformat() if user.identity_linked_at else None,
    }


def list_admin_users(db: Session, ctx: AuthContext) -> List[Dict[str, Any]]:
    _require_read(ctx)
    users = (
        db.query(AdminUser)
        .options(joinedload(AdminUser.location_assignments).joinedload(UserLocationAssignment.location))
        .order_by(AdminUser.email)
        .all()
    )
    return [_serialize_user(u) for u in users]


def _validate_role_locations(role: str, location_ids: List[int]) -> None:
    if role in (AdminRole.SITE_ADMIN.value, AdminRole.SECURITY.value):
        if not location_ids:
            raise AdminUserError(
                "validation_error",
                "Site Admin and Security roles require at least one assigned location.",
            )
    try:
        AdminRole(role)
    except ValueError:
        raise AdminUserError("validation_error", "Invalid role.")


def _assign_locations(db: Session, user: AdminUser, location_ids: List[int]) -> None:
    valid_ids = {
        row.id
        for row in db.query(Location.id).filter(Location.id.in_(location_ids), Location.is_active.is_(True)).all()
    }
    if len(valid_ids) != len(set(location_ids)):
        raise AdminUserError("validation_error", "One or more assigned locations are invalid.")
    user.location_assignments.clear()
    for lid in sorted(valid_ids):
        user.location_assignments.append(UserLocationAssignment(location_id=lid))
    db.flush()


def create_admin_user(
    db: Session,
    ctx: AuthContext,
    email: str,
    display_name: str,
    role: str,
    location_ids: List[int],
    is_active: bool = True,
    temporary_password: Optional[str] = None,
    generate_password: bool = False,
    force_password_change: bool = True,
) -> Dict[str, Any]:
    _require_manage(ctx)
    _require_privileged_role_assignment(ctx, role)
    normalized = normalize_email(email)
    if not normalized or "@" not in normalized:
        raise AdminUserError("validation_error", "A valid company email is required.")
    existing = db.query(AdminUser).filter(AdminUser.email == normalized).first()
    if existing:
        raise AdminUserError("duplicate_email", "An admin user with this email already exists.")
    _validate_role_locations(role, location_ids)

    password = temporary_password
    if generate_password:
        password = generate_temporary_password()
    if not password:
        raise AdminUserError("validation_error", "A temporary password is required for new users.")
    _validate_password(password)

    user = AdminUser(
        email=normalized,
        display_name=(display_name or "").strip() or None,
        role=role,
        is_owner=False,
        is_active=is_active,
        auth_provider=VMS_NATIVE_AUTH_PROVIDER,
        force_password_change=force_password_change,
    )
    db.add(user)
    db.flush()
    set_user_password(db, user, password, clear_force_change=not force_password_change)
    if location_ids:
        _assign_locations(db, user, location_ids)

    audit = AuditService(db)
    audit.record(
        action="USER_CREATED",
        entity_type="admin_user",
        entity_id=str(user.id),
        actor_id=ctx.user_id,
        actor_email=ctx.email,
        after_value={"email": normalized, "role": role, "is_active": is_active},
    )
    db.refresh(user)
    return _serialize_user(user)


def update_admin_user(
    db: Session,
    ctx: AuthContext,
    user_id: int,
    display_name: Optional[str] = None,
    role: Optional[str] = None,
    location_ids: Optional[List[int]] = None,
    is_active: Optional[bool] = None,
) -> Dict[str, Any]:
    _require_manage(ctx)
    user = (
        db.query(AdminUser)
        .options(joinedload(AdminUser.location_assignments).joinedload(UserLocationAssignment.location))
        .filter(AdminUser.id == user_id)
        .first()
    )
    if not user:
        raise AdminUserError("not_found", "Admin user not found.", 404)

    if user.is_owner:
        if role and role != user.role:
            raise AdminUserError("owner_protected", "The owner account role cannot be changed.", 403)
        if is_active is False:
            raise AdminUserError("owner_protected", "The owner account cannot be deactivated.", 403)

    new_role = role or user.role
    if role:
        _require_privileged_role_assignment(ctx, new_role)
        _validate_role_locations(new_role, location_ids or [a.location_id for a in user.location_assignments])
        if user.role != new_role:
            audit = AuditService(db)
            audit.record(
                action="ROLE_CHANGED",
                entity_type="admin_user",
                entity_id=str(user.id),
                actor_id=ctx.user_id,
                actor_email=ctx.email,
                before_value={"role": user.role},
                after_value={"role": new_role},
            )
        user.role = new_role
    if display_name is not None:
        user.display_name = display_name.strip() or None
    if location_ids is not None:
        _validate_role_locations(new_role, location_ids)
        prev_ids = sorted([a.location_id for a in user.location_assignments])
        _assign_locations(db, user, location_ids)
        new_ids = sorted(location_ids)
        if prev_ids != new_ids:
            audit = AuditService(db)
            for lid in set(new_ids) - set(prev_ids):
                audit.record(
                    action="LOCATION_ACCESS_ADDED",
                    entity_type="admin_user",
                    entity_id=str(user.id),
                    actor_id=ctx.user_id,
                    actor_email=ctx.email,
                    after_value={"location_id": lid},
                )
            for lid in set(prev_ids) - set(new_ids):
                audit.record(
                    action="LOCATION_ACCESS_REMOVED",
                    entity_type="admin_user",
                    entity_id=str(user.id),
                    actor_id=ctx.user_id,
                    actor_email=ctx.email,
                    before_value={"location_id": lid},
                )
    if is_active is not None and not user.is_owner:
        if is_active and not user.is_active:
            AuditService(db).record(
                action="USER_REACTIVATED",
                entity_type="admin_user",
                entity_id=str(user.id),
                actor_id=ctx.user_id,
                actor_email=ctx.email,
            )
        elif not is_active and user.is_active:
            AuditService(db).record(
                action="USER_DISABLED",
                entity_type="admin_user",
                entity_id=str(user.id),
                actor_id=ctx.user_id,
                actor_email=ctx.email,
            )
        user.is_active = is_active

    audit = AuditService(db)
    audit.record(
        action="USER_UPDATED",
        entity_type="admin_user",
        entity_id=str(user.id),
        actor_id=ctx.user_id,
        actor_email=ctx.email,
        after_value={"role": user.role, "is_active": user.is_active},
    )
    db.refresh(user)
    return _serialize_user(user)


def deactivate_admin_user(db: Session, ctx: AuthContext, user_id: int) -> Dict[str, Any]:
    return update_admin_user(db, ctx, user_id, is_active=False)


def reset_admin_user_password(
    db: Session,
    ctx: AuthContext,
    user_id: int,
    temporary_password: str,
    confirm_password: str,
    force_password_change: bool = True,
) -> Dict[str, Any]:
    _require_manage(ctx)
    _validate_password(temporary_password)
    _validate_password_match(temporary_password, confirm_password)
    user = (
        db.query(AdminUser)
        .options(joinedload(AdminUser.location_assignments).joinedload(UserLocationAssignment.location))
        .filter(AdminUser.id == user_id)
        .first()
    )
    if not user:
        raise AdminUserError("not_found", "Admin user not found.", 404)
    set_user_password(db, user, temporary_password, clear_force_change=not force_password_change)
    user.force_password_change = force_password_change
    user.auth_provider = VMS_NATIVE_AUTH_PROVIDER
    invalidate_vms_native_sessions(user)
    AuditService(db).record(
        action="USER_PASSWORD_RESET",
        entity_type="admin_user",
        entity_id=str(user.id),
        actor_id=ctx.user_id,
        actor_email=ctx.email,
        metadata={"target_user_id": user.id},
    )
    db.refresh(user)
    return _serialize_user(user)
