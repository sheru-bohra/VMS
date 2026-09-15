from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.domain.enums import AdminRole, Permission, get_permissions_for_role, role_has_permission
from app.domain.models import AdminUser


@dataclass
class AuthContext:
    user_id: int
    email: str
    display_name: Optional[str]
    role: AdminRole
    is_owner: bool
    permissions: frozenset
    location_ids: List[int]
    auth_provider: str = "dev"


class AuthenticationError(Exception):
    pass


class AuthorizationError(Exception):
    pass


def get_user_by_email(db: Session, email: str) -> Optional[AdminUser]:
    return db.query(AdminUser).filter(AdminUser.email == email, AdminUser.is_active.is_(True)).first()


def _build_context(user: AdminUser) -> AuthContext:
    role = AdminRole(user.role)
    location_ids = [a.location_id for a in user.location_assignments]
    return AuthContext(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=role,
        is_owner=user.is_owner,
        permissions=get_permissions_for_role(role),
        location_ids=location_ids,
        auth_provider=user.auth_provider or "dev",
    )


def authenticate_dev_user(db: Session, override_email: Optional[str] = None) -> Optional[AuthContext]:
    if settings.auth_mode != "dev":
        return None
    if not settings.dev_auth_enabled or settings.is_production:
        return None
    email = override_email or settings.dev_auth_user or settings.dev_auth_email
    user = get_user_by_email(db, email)
    if not user:
        return None
    return _build_context(user)


def build_auth_context(user: AdminUser) -> AuthContext:
    return _build_context(user)


def require_permission(ctx: AuthContext, permission: Permission) -> None:
    if not role_has_permission(ctx.role, permission):
        raise AuthorizationError(f"Permission denied: {permission.value}")
