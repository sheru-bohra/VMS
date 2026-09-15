from __future__ import annotations

from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.application.admin_user_service import (
    AdminUserError,
    create_admin_user,
    deactivate_admin_user,
    list_admin_users,
    reset_admin_user_password,
    update_admin_user,
)
from app.application.auth_service import AuthContext
from app.core.errors import APIError
from app.infrastructure.database import get_db
from app.presentation.dependencies import PermissionChecker
from app.domain.enums import Permission

router = APIRouter(prefix="/administration/users", tags=["administration"])


class AdminUserLocation(BaseModel):
    id: int
    name: str
    code: str
    city: Optional[str] = None


class AdminUserResponse(BaseModel):
    id: int
    email: str
    display_name: Optional[str] = None
    role: str
    is_owner: bool
    is_active: bool
    location_ids: List[int]
    assigned_locations: List[AdminUserLocation] = []
    entra_linked: bool
    auth_provider: Optional[str] = None
    force_password_change: bool = False
    sso_status: Optional[str] = None
    access_status: Optional[str] = None
    last_login_at: Optional[str] = None
    identity_linked_at: Optional[str] = None


class CreateAdminUserRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=255)
    display_name: Optional[str] = Field(None, max_length=255)
    role: str = Field(..., min_length=4, max_length=50)
    location_ids: List[int] = Field(default_factory=list)
    is_active: bool = True
    temporary_password: Optional[str] = Field(None, min_length=12, max_length=256)
    generate_password: bool = False
    force_password_change: bool = True


class UpdateAdminUserRequest(BaseModel):
    display_name: Optional[str] = Field(None, max_length=255)
    role: Optional[str] = Field(None, max_length=50)
    location_ids: Optional[List[int]] = None
    is_active: Optional[bool] = None


class ResetPasswordRequest(BaseModel):
    temporary_password: str = Field(..., min_length=12, max_length=256)
    confirm_password: str = Field(..., min_length=12, max_length=256)
    force_password_change: bool = True


def _handle_error(exc: AdminUserError) -> None:
    raise APIError(exc.status_code, exc.code, exc.message)


@router.get("", response_model=List[AdminUserResponse])
def get_admin_users(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(PermissionChecker(Permission.ADMINS_READ))],
) -> List[AdminUserResponse]:
    try:
        rows = list_admin_users(db, user)
        return [AdminUserResponse(**row) for row in rows]
    except AdminUserError as exc:
        _handle_error(exc)
        return []


@router.post("", response_model=AdminUserResponse)
def post_admin_user(
    body: CreateAdminUserRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(PermissionChecker(Permission.ADMINS_MANAGE))],
) -> AdminUserResponse:
    try:
        row = create_admin_user(
            db,
            user,
            email=body.email,
            display_name=body.display_name or "",
            role=body.role,
            location_ids=body.location_ids,
            is_active=body.is_active,
            temporary_password=body.temporary_password,
            generate_password=body.generate_password,
            force_password_change=body.force_password_change,
        )
        db.commit()
        return AdminUserResponse(**row)
    except AdminUserError as exc:
        db.rollback()
        _handle_error(exc)
        raise


@router.patch("/{user_id}", response_model=AdminUserResponse)
def patch_admin_user(
    user_id: int,
    body: UpdateAdminUserRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(PermissionChecker(Permission.ADMINS_MANAGE))],
) -> AdminUserResponse:
    try:
        row = update_admin_user(
            db,
            user,
            user_id,
            display_name=body.display_name,
            role=body.role,
            location_ids=body.location_ids,
            is_active=body.is_active,
        )
        db.commit()
        return AdminUserResponse(**row)
    except AdminUserError as exc:
        db.rollback()
        _handle_error(exc)
        raise


@router.post("/{user_id}/deactivate", response_model=AdminUserResponse)
def post_deactivate_admin_user(
    user_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(PermissionChecker(Permission.ADMINS_MANAGE))],
) -> AdminUserResponse:
    try:
        row = deactivate_admin_user(db, user, user_id)
        db.commit()
        return AdminUserResponse(**row)
    except AdminUserError as exc:
        db.rollback()
        _handle_error(exc)
        raise


@router.post("/{user_id}/reset-password", response_model=AdminUserResponse)
def post_reset_admin_user_password(
    user_id: int,
    body: ResetPasswordRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(PermissionChecker(Permission.ADMINS_MANAGE))],
) -> AdminUserResponse:
    try:
        row = reset_admin_user_password(
            db,
            user,
            user_id,
            temporary_password=body.temporary_password,
            confirm_password=body.confirm_password,
            force_password_change=body.force_password_change,
        )
        db.commit()
        return AdminUserResponse(**row)
    except AdminUserError as exc:
        db.rollback()
        _handle_error(exc)
        raise
