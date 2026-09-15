from __future__ import annotations

from typing import Annotated, Optional

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from app.application.auth_service import AuthContext, authenticate_dev_user
from app.application.direct_owner_auth_service import (
    DirectOwnerAuthError,
    authenticate_direct_owner_token,
    is_direct_owner_token,
)
from app.application.entra_auth_service import EntraAuthError, resolve_entra_user
from app.application.entra_token_validator import EntraTokenError, validate_entra_id_token
from app.application.audit_service import AuditService
from app.application.vms_native_auth_service import (
    VmsNativeAuthError,
    authenticate_vms_native_token,
    is_vms_native_token,
)
from app.core.config import settings
from app.core.errors import APIError
from app.domain.models import AdminUser
from app.infrastructure.database import get_db
from app.domain.enums import Permission, role_has_permission

_PASSWORD_CHANGE_ALLOWED_PATHS = frozenset(
    {
        "/api/auth/set-password",
        "/api/auth/logout",
        "/api/me",
    }
)


def _enforce_password_change(db: Session, request: Request, user_id: int) -> None:
    path = request.url.path
    if path in _PASSWORD_CHANGE_ALLOWED_PATHS:
        return
    admin_row = db.query(AdminUser).filter(AdminUser.id == user_id).first()
    if admin_row and admin_row.force_password_change:
        raise APIError(
            403,
            "PASSWORD_CHANGE_REQUIRED",
            "You must set a new password before continuing.",
        )


def _authenticate_bearer(db: Session, token: str) -> AuthContext:
    if settings.resolved_vms_native_auth_enabled and is_vms_native_token(token):
        try:
            return authenticate_vms_native_token(db, token)
        except VmsNativeAuthError as exc:
            raise APIError(exc.status_code, exc.code, exc.message)

    if settings.auth_mode == "entra" and settings.direct_owner_auth_enabled and is_direct_owner_token(token):
        try:
            return authenticate_direct_owner_token(db, token)
        except DirectOwnerAuthError as exc:
            raise APIError(exc.status_code, exc.code, exc.message)

    if settings.entra_auth_enabled or settings.auth_mode == "entra":
        try:
            claims = validate_entra_id_token(token)
            return resolve_entra_user(db, claims)
        except EntraTokenError as exc:
            if exc.code == "AUTH_WRONG_TENANT":
                AuditService(db).record(action="WRONG_TENANT_LOGIN", entity_type="auth")
            else:
                AuditService(db).record(
                    action="SSO_LOGIN_FAILED",
                    entity_type="auth",
                    metadata={"code": exc.code},
                )
            raise APIError(exc.status_code, exc.code, exc.message)
        except EntraAuthError as exc:
            raise APIError(exc.status_code, exc.code, exc.message)

    raise APIError(401, "AUTH_TOKEN_INVALID", "Authentication required.")


def get_current_user(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    authorization: Annotated[Optional[str], Header()] = None,
    x_dev_user_email: Annotated[Optional[str], Header(alias="X-Dev-User-Email")] = None,
) -> AuthContext:
    if settings.auth_mode == "dev":
        ctx = authenticate_dev_user(db, override_email=x_dev_user_email)
        if ctx:
            return ctx
        raise APIError(401, "unauthorized", "Authentication required.")

    if settings.auth_mode in ("vms_native", "entra"):
        if x_dev_user_email and not settings.is_production:
            pass
        if not authorization or not authorization.lower().startswith("bearer "):
            raise APIError(401, "AUTH_TOKEN_MISSING", "Authentication required.")
        token = authorization.split(" ", 1)[1].strip()
        if not token:
            raise APIError(401, "AUTH_TOKEN_MISSING", "Authentication required.")
        ctx = _authenticate_bearer(db, token)
        db.commit()
        _enforce_password_change(db, request, ctx.user_id)
        return ctx

    raise APIError(401, "unauthorized", "Authentication required.")


def get_optional_user(
    db: Annotated[Session, Depends(get_db)],
) -> Optional[AuthContext]:
    if settings.auth_mode == "dev":
        return authenticate_dev_user(db)
    return None


def require_auth(user: Annotated[AuthContext, Depends(get_current_user)]) -> AuthContext:
    return user


class PermissionChecker:
    def __init__(self, permission: Permission):
        self.permission = permission

    def __call__(self, user: AuthContext = Depends(get_current_user)) -> AuthContext:
        if not role_has_permission(user.role, self.permission):
            raise APIError(403, "forbidden", f"Permission denied: {self.permission.value}")
        return user
