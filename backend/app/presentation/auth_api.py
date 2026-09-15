from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.application.audit_service import AuditService
from app.application.auth_service import AuthContext
from app.application.password_policy import validate_password_confirmation, validate_password_policy
from app.application.rate_limit_service import check_vms_native_password_change_rate_limit
from app.application.vms_native_auth_service import (
    VMS_NATIVE_AUTH_PROVIDER,
    authenticate_vms_native_login,
    change_own_password,
    invalidate_vms_native_sessions,
    is_vms_native_provider,
    set_user_password,
)
from app.core.errors import APIError
from app.domain.enums import AdminRole
from app.domain.models import AdminUser
from app.infrastructure.database import get_db
from app.presentation.dependencies import require_auth

router = APIRouter(tags=["auth"])


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=1, max_length=256)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    force_password_change: bool = False


class SetPasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=12, max_length=256)
    confirm_password: str = Field(..., min_length=12, max_length=256)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=256)
    new_password: str = Field(..., min_length=12, max_length=256)
    confirm_password: str = Field(..., min_length=12, max_length=256)


def _commit_invalid_credentials(db: Session, exc: APIError) -> None:
    if exc.code == "invalid_credentials":
        db.commit()
    else:
        db.rollback()


@router.post("/auth/login", response_model=LoginResponse)
def staff_login(
    body: LoginRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    try:
        token, expires_in, force_change = authenticate_vms_native_login(
            db, body.email, body.password, request
        )
        db.commit()
        return LoginResponse(
            access_token=token,
            expires_in=expires_in,
            force_password_change=force_change,
        )
    except APIError as exc:
        _commit_invalid_credentials(db, exc)
        raise
    except Exception:
        db.rollback()
        raise APIError(401, "invalid_credentials", "Invalid email or password.")


@router.post("/auth/owner-login", response_model=LoginResponse)
def owner_login(
    body: LoginRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    return staff_login(body, request, db)


@router.post("/auth/set-password")
def set_password(
    body: SetPasswordRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
):
    admin_row = db.query(AdminUser).filter(AdminUser.id == user.user_id).first()
    if not admin_row:
        raise APIError(401, "unauthorized", "Authentication required.")
    check_vms_native_password_change_rate_limit(request, admin_row.email)
    validate_password_policy(body.new_password)
    validate_password_confirmation(body.new_password, body.confirm_password)
    set_user_password(db, admin_row, body.new_password, clear_force_change=True)
    AuditService(db).record(
        action="PASSWORD_CHANGED",
        entity_type="admin_user",
        entity_id=str(admin_row.id),
        actor_id=user.user_id,
        actor_email=user.email,
        metadata={"auth_provider": VMS_NATIVE_AUTH_PROVIDER, "flow": "forced_set_password"},
    )
    db.commit()
    return {"status": "ok"}


@router.post("/auth/change-password")
def change_password(
    body: ChangePasswordRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
):
    if user.role != AdminRole.GLOBAL_ADMIN.value:
        raise APIError(403, "forbidden", "Only Global Administrators can change their password here.")
    admin_row = db.query(AdminUser).filter(AdminUser.id == user.user_id).first()
    if not admin_row or not is_vms_native_provider(admin_row.auth_provider):
        raise APIError(403, "forbidden", "Password change is not available for this account.")
    check_vms_native_password_change_rate_limit(request, admin_row.email)
    try:
        change_own_password(
            db,
            admin_row,
            body.current_password,
            body.new_password,
            body.confirm_password,
        )
    except APIError:
        db.rollback()
        raise
    AuditService(db).record(
        action="PASSWORD_CHANGED",
        entity_type="admin_user",
        entity_id=str(admin_row.id),
        actor_id=user.user_id,
        actor_email=user.email,
        metadata={"auth_provider": VMS_NATIVE_AUTH_PROVIDER, "flow": "self_service"},
    )
    db.commit()
    return {"status": "ok"}


@router.post("/auth/logout")
def auth_logout(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
):
    if user.auth_provider in (VMS_NATIVE_AUTH_PROVIDER, "direct"):
        admin_row = db.query(AdminUser).filter(AdminUser.id == user.user_id).first()
        if admin_row:
            invalidate_vms_native_sessions(admin_row)
    AuditService(db).record(
        action="LOGOUT",
        entity_type="admin_user",
        entity_id=str(user.user_id),
        actor_id=user.user_id,
        actor_email=user.email,
        metadata={"auth_provider": user.auth_provider},
    )
    db.commit()
    return {"status": "ok"}
