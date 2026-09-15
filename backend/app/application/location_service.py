"""Location directory management."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.application.audit_service import AuditService
from app.application.auth_service import AuthContext
from app.application.registration_url_service import build_registration_public_url
from app.application.token_service import generate_public_token
from app.domain.enums import AdminRole, EmergencyEventStatus, Permission, VisitStatus, role_has_permission
from app.domain.models import AdminUser, EmergencyEvent, Location, LocationAccessConfiguration, UserLocationAssignment, Visit


class LocationError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _require_manage(ctx: AuthContext) -> None:
    if not role_has_permission(ctx.role, Permission.LOCATIONS_MANAGE):
        raise LocationError("forbidden", "You do not have permission to manage locations.", 403)


def _normalize_code(code: str) -> str:
    return (code or "").strip().upper()


def _staff_counts(db: Session, location_ids: List[int]) -> Dict[int, Dict[str, int]]:
    if not location_ids:
        return {}
    rows = (
        db.query(
            UserLocationAssignment.location_id,
            AdminUser.role,
            func.count(AdminUser.id),
        )
        .join(AdminUser, AdminUser.id == UserLocationAssignment.admin_user_id)
        .filter(
            UserLocationAssignment.location_id.in_(location_ids),
            AdminUser.role.in_([AdminRole.SITE_ADMIN.value, AdminRole.SECURITY.value]),
        )
        .group_by(UserLocationAssignment.location_id, AdminUser.role)
        .all()
    )
    result: Dict[int, Dict[str, int]] = {lid: {"site_admin_count": 0, "security_count": 0, "site_staff_count": 0} for lid in location_ids}
    for location_id, role, count in rows:
        bucket = result.setdefault(
            location_id,
            {"site_admin_count": 0, "security_count": 0, "site_staff_count": 0},
        )
        if role == AdminRole.SITE_ADMIN.value:
            bucket["site_admin_count"] = count
        elif role == AdminRole.SECURITY.value:
            bucket["security_count"] = count
        bucket["site_staff_count"] = bucket["site_admin_count"] + bucket["security_count"]
    return result


def serialize_location(
    loc: Location,
    *,
    include_token: bool = False,
    staff_counts: Optional[Dict[str, int]] = None,
) -> Dict[str, Any]:
    token = loc.public_registration_token if include_token else None
    url = build_registration_public_url(token) if include_token and token else None
    counts = staff_counts or {"site_admin_count": 0, "security_count": 0, "site_staff_count": 0}
    return {
        "id": loc.id,
        "name": loc.name,
        "code": loc.code,
        "city": loc.city,
        "timezone": loc.timezone,
        "is_active": loc.is_active,
        "is_development_seed": loc.is_development_seed,
        "registration_enabled": loc.registration_enabled,
        "public_registration_token": token,
        "registration_url": url,
        "site_staff_count": counts.get("site_staff_count", 0),
        "site_admin_count": counts.get("site_admin_count", 0),
        "security_count": counts.get("security_count", 0),
    }


def create_location(
    db: Session,
    ctx: AuthContext,
    name: str,
    code: str,
    timezone: str,
    registration_enabled: bool = True,
) -> Dict[str, Any]:
    _require_manage(ctx)
    clean_name = (name or "").strip()
    clean_code = _normalize_code(code)
    clean_tz = (timezone or "").strip()
    if not clean_name:
        raise LocationError("validation_error", "Location name is required.")
    if not clean_code:
        raise LocationError("validation_error", "Location code is required.")
    if not clean_tz:
        raise LocationError("validation_error", "Timezone is required.")

    existing_code = db.query(Location).filter(Location.code == clean_code).first()
    if existing_code:
        raise LocationError("duplicate_code", "A location with this code already exists.", 409)

    existing_name = (
        db.query(Location)
        .filter(Location.is_active.is_(True), func.lower(Location.name) == clean_name.lower())
        .first()
    )
    if existing_name:
        raise LocationError("duplicate_name", "An active location with this name already exists.", 409)

    token = generate_public_token() if registration_enabled else None
    loc = Location(
        name=clean_name,
        code=clean_code,
        city=None,
        timezone=clean_tz,
        is_active=True,
        is_development_seed=False,
        registration_enabled=registration_enabled,
        public_registration_token=token,
    )
    db.add(loc)
    db.flush()

    db.add(
        LocationAccessConfiguration(
            location_id=loc.id,
            access_control_enabled=False,
            provider_key="disabled",
            credential_grace_minutes=30,
            max_credential_duration_minutes=720,
            is_active=True,
        )
    )

    AuditService(db).record(
        action="LOCATION_CREATED",
        entity_type="location",
        entity_id=str(loc.id),
        actor_id=ctx.user_id,
        actor_email=ctx.email,
        location_id=loc.id,
        after_value={
            "name": clean_name,
            "code": clean_code,
            "timezone": clean_tz,
            "registration_enabled": registration_enabled,
        },
    )
    db.refresh(loc)
    counts = _staff_counts(db, [loc.id])
    return serialize_location(loc, include_token=True, staff_counts=counts.get(loc.id))


def get_staff_counts_for_locations(db: Session, location_ids: List[int]) -> Dict[int, Dict[str, int]]:
    return _staff_counts(db, location_ids)


ONSITE_BLOCKER_STATUSES = frozenset({
    VisitStatus.ONSITE.value,
    VisitStatus.CHECKED_IN.value,
    VisitStatus.OVERSTAYED.value,
})

ACTIVE_WORKFLOW_STATUSES = frozenset({
    VisitStatus.PENDING_APPROVAL.value,
    VisitStatus.APPROVED.value,
    VisitStatus.EXPECTED.value,
    VisitStatus.ARRIVED.value,
    VisitStatus.CHECKED_IN.value,
    VisitStatus.ONSITE.value,
    VisitStatus.OVERSTAYED.value,
    VisitStatus.DRAFT.value,
})

FUTURE_VISIT_STATUSES = frozenset({
    VisitStatus.APPROVED.value,
    VisitStatus.EXPECTED.value,
    VisitStatus.ARRIVED.value,
})


def _get_location_for_manage(db: Session, location_id: int) -> Location:
    loc = db.query(Location).filter(Location.id == location_id).first()
    if not loc:
        raise LocationError("not_found", "Location not found.", 404)
    return loc


def _retire_blocker_counts(db: Session, location_id: int) -> Dict[str, Any]:
    staff_counts = _staff_counts(db, [location_id]).get(location_id, {})
    assigned_staff = staff_counts.get("site_staff_count", 0)
    onsite_visitors = (
        db.query(Visit)
        .filter(Visit.location_id == location_id, Visit.status.in_(ONSITE_BLOCKER_STATUSES))
        .count()
    )
    pending_approvals = (
        db.query(Visit)
        .filter(Visit.location_id == location_id, Visit.status == VisitStatus.PENDING_APPROVAL.value)
        .count()
    )
    future_visits = (
        db.query(Visit)
        .filter(Visit.location_id == location_id, Visit.status.in_(FUTURE_VISIT_STATUSES))
        .count()
    )
    active_emergency = (
        db.query(EmergencyEvent)
        .filter(
            EmergencyEvent.location_id == location_id,
            EmergencyEvent.status == EmergencyEventStatus.ACTIVE.value,
        )
        .first()
        is not None
    )
    active_workflow_visits = (
        db.query(Visit)
        .filter(Visit.location_id == location_id, Visit.status.in_(ACTIVE_WORKFLOW_STATUSES))
        .count()
    )
    return {
        "assigned_staff": assigned_staff,
        "onsite_visitors": onsite_visitors,
        "pending_approvals": pending_approvals,
        "future_visits": future_visits,
        "active_emergency": active_emergency,
        "active_workflow_visits": active_workflow_visits,
    }


def _validate_retire_blockers(db: Session, location: Location, counts: Dict[str, Any]) -> None:
    if counts["assigned_staff"] > 0:
        raise LocationError(
            "LOCATION_HAS_ASSIGNED_STAFF",
            "Remove assigned Site Admin and Security access before deleting this location.",
            409,
        )
    if counts["onsite_visitors"] > 0:
        raise LocationError(
            "LOCATION_HAS_ONSITE_VISITORS",
            f"Cannot delete {location.name} while {counts['onsite_visitors']} visitor(s) are currently onsite. "
            "Check out visitors before deleting this location.",
            409,
        )
    if counts["active_emergency"]:
        raise LocationError(
            "LOCATION_HAS_ACTIVE_EMERGENCY",
            f"Cannot delete {location.name} while an emergency event is active.",
            409,
        )
    if counts["active_workflow_visits"] > 0:
        raise LocationError(
            "LOCATION_HAS_ACTIVE_VISITS",
            f"Cannot delete {location.name} while active visits, approvals, or expected visitors remain. "
            "Resolve or cancel operational visits first.",
            409,
        )


def get_location_retire_summary(
    db: Session,
    ctx: AuthContext,
    location_id: int,
) -> Dict[str, Any]:
    _require_manage(ctx)
    loc = _get_location_for_manage(db, location_id)
    counts = _retire_blocker_counts(db, location_id)
    blockers: List[str] = []
    if counts["assigned_staff"] > 0:
        blockers.append("LOCATION_HAS_ASSIGNED_STAFF")
    if counts["onsite_visitors"] > 0:
        blockers.append("LOCATION_HAS_ONSITE_VISITORS")
    if counts["active_emergency"]:
        blockers.append("LOCATION_HAS_ACTIVE_EMERGENCY")
    if counts["active_workflow_visits"] > 0:
        blockers.append("LOCATION_HAS_ACTIVE_VISITS")
    return {
        "location_id": loc.id,
        "name": loc.name,
        "code": loc.code,
        "is_active": loc.is_active,
        "assigned_staff": counts["assigned_staff"],
        "onsite_visitors": counts["onsite_visitors"],
        "pending_approvals": counts["pending_approvals"],
        "future_visits": counts["future_visits"],
        "active_emergency": counts["active_emergency"],
        "can_retire": len(blockers) == 0 and loc.is_active,
        "blockers": blockers,
    }


def retire_location(
    db: Session,
    ctx: AuthContext,
    location_id: int,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    _require_manage(ctx)
    loc = _get_location_for_manage(db, location_id)
    if not loc.is_active:
        return {"location_id": loc.id, "status": "RETIRED", "code": loc.code}

    counts = _retire_blocker_counts(db, location_id)
    _validate_retire_blockers(db, loc, counts)

    prev_registration_enabled = loc.registration_enabled
    loc.is_active = False
    loc.registration_enabled = False
    db.flush()

    audit_payload: Dict[str, Any] = {"code": loc.code, "name": loc.name}
    if reason and reason.strip():
        audit_payload["reason"] = reason.strip()[:500]

    AuditService(db).record(
        action="LOCATION_DEACTIVATED",
        entity_type="location",
        entity_id=str(loc.id),
        actor_id=ctx.user_id,
        actor_email=ctx.email,
        location_id=loc.id,
        before_value={"is_active": True, "registration_enabled": prev_registration_enabled},
        after_value={"is_active": False, "registration_enabled": False, **audit_payload},
    )
    return {"location_id": loc.id, "status": "RETIRED", "code": loc.code}
