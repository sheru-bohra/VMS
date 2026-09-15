"""Per-location SITE_ADMIN / SECURITY staff assignment."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session, joinedload

from app.application.audit_service import AuditService
from app.application.auth_service import AuthContext
from app.application.bootstrap import OWNER_EMAIL
from app.application.location_service import LocationError, _require_manage
from app.application.registration_service import normalize_email
from app.domain.enums import AdminRole
from app.domain.models import AdminUser, Location, UserLocationAssignment


SITE_STAFF_ROLES = frozenset({AdminRole.SITE_ADMIN.value, AdminRole.SECURITY.value})
PRIVILEGED_ROLES = frozenset({AdminRole.GLOBAL_ADMIN.value, AdminRole.HEAD_ADMIN.value})


def _serialize_staff_member(user: AdminUser, assignment: UserLocationAssignment) -> Dict[str, Any]:
    return {
        "user_id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role,
        "is_active": user.is_active,
        "assigned_at": assignment.created_at.isoformat() if assignment.created_at else None,
    }


def list_location_staff(db: Session, ctx: AuthContext, location_id: int) -> List[Dict[str, Any]]:
    _require_manage(ctx)
    location = db.query(Location).filter(Location.id == location_id, Location.is_active.is_(True)).first()
    if not location:
        raise LocationError("not_found", "Location not found.", 404)

    rows = (
        db.query(AdminUser, UserLocationAssignment)
        .join(UserLocationAssignment, UserLocationAssignment.admin_user_id == AdminUser.id)
        .filter(
            UserLocationAssignment.location_id == location_id,
            AdminUser.role.in_(list(SITE_STAFF_ROLES)),
        )
        .order_by(AdminUser.display_name, AdminUser.email)
        .all()
    )
    return [_serialize_staff_member(user, assignment) for user, assignment in rows]


def assign_location_staff(
    db: Session,
    ctx: AuthContext,
    location_id: int,
    email: str,
    display_name: str,
    role: str,
    extra_fields: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    _require_manage(ctx)
    if extra_fields:
        forbidden = {k for k in extra_fields if k in ("is_owner", "permissions", "global_scope", "auth_provider", "entra_object_id")}
        if forbidden:
            raise LocationError("validation_error", "Invalid fields in request.", 400)

    if role not in SITE_STAFF_ROLES:
        raise LocationError(
            "validation_error",
            "Only SITE_ADMIN and SECURITY roles can be assigned through location staff management.",
            400,
        )

    location = db.query(Location).filter(Location.id == location_id, Location.is_active.is_(True)).first()
    if not location:
        raise LocationError("not_found", "Location not found.", 404)

    normalized = normalize_email(email)
    if not normalized or "@" not in normalized:
        raise LocationError("validation_error", "A valid corporate email is required.")

    clean_name = (display_name or "").strip()
    if not clean_name:
        raise LocationError("validation_error", "Display name is required.")

    user = db.query(AdminUser).filter(AdminUser.email == normalized).first()
    audit = AuditService(db)
    created = False

    if user:
        if user.is_owner or normalized == OWNER_EMAIL:
            raise LocationError("owner_protected", "The owner account cannot be assigned through location staff management.", 403)
        if user.role in PRIVILEGED_ROLES:
            raise LocationError(
                "higher_role",
                "This user already has a higher-level VMS role.",
                400,
            )
        if user.role != role:
            raise LocationError(
                "role_mismatch",
                f"This user already has the {user.role} role. Assign them as {user.role} or update their role through Users & Access.",
                400,
            )
    else:
        user = AdminUser(
            email=normalized,
            display_name=clean_name,
            role=role,
            is_owner=False,
            is_active=True,
        )
        db.add(user)
        db.flush()
        created = True
        audit.record(
            action="SITE_USER_CREATED",
            entity_type="admin_user",
            entity_id=str(user.id),
            actor_id=ctx.user_id,
            actor_email=ctx.email,
            location_id=location_id,
            after_value={"email": normalized, "role": role},
        )

    existing_assignment = (
        db.query(UserLocationAssignment)
        .filter(
            UserLocationAssignment.admin_user_id == user.id,
            UserLocationAssignment.location_id == location_id,
        )
        .first()
    )
    if existing_assignment:
        return _serialize_staff_member(user, existing_assignment)

    assignment = UserLocationAssignment(admin_user_id=user.id, location_id=location_id)
    db.add(assignment)
    db.flush()

    audit.record(
        action="LOCATION_USER_ASSIGNED",
        entity_type="admin_user",
        entity_id=str(user.id),
        actor_id=ctx.user_id,
        actor_email=ctx.email,
        location_id=location_id,
        after_value={"role": user.role, "location_id": location_id},
    )

    if created:
        db.refresh(user)
    return _serialize_staff_member(user, assignment)


def remove_location_staff(db: Session, ctx: AuthContext, location_id: int, user_id: int) -> None:
    _require_manage(ctx)
    location = db.query(Location).filter(Location.id == location_id).first()
    if not location:
        raise LocationError("not_found", "Location not found.", 404)

    user = (
        db.query(AdminUser)
        .options(joinedload(AdminUser.location_assignments))
        .filter(AdminUser.id == user_id)
        .first()
    )
    if not user:
        raise LocationError("not_found", "Staff user not found.", 404)

    if user.is_owner:
        raise LocationError("owner_protected", "The owner account cannot be modified through location staff management.", 403)

    assignment = (
        db.query(UserLocationAssignment)
        .filter(
            UserLocationAssignment.admin_user_id == user_id,
            UserLocationAssignment.location_id == location_id,
        )
        .first()
    )
    if not assignment:
        raise LocationError("not_found", "This user is not assigned to this location.", 404)

    db.delete(assignment)
    db.flush()

    AuditService(db).record(
        action="LOCATION_USER_REMOVED",
        entity_type="admin_user",
        entity_id=str(user.id),
        actor_id=ctx.user_id,
        actor_email=ctx.email,
        location_id=location_id,
        before_value={"role": user.role, "location_id": location_id},
    )
