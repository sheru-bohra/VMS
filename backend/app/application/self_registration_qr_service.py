"""Staff reception QR configuration and location-scoped self-registration stats."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.application.auth_service import AuthContext
from app.application.registration_url_service import build_registration_public_url, is_localhost_public_url
from app.application.site_scope_service import can_access_location, get_allowed_location_ids
from app.application.timezone_service import get_location_day_bounds
from app.core.config import settings
from app.domain.enums import VisitStatus
from app.domain.models import Location, Visit


class SelfRegistrationQrError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _company_label() -> str:
    return "PayU"


def _accessible_locations(db: Session, ctx: AuthContext) -> List[Location]:
    allowed = get_allowed_location_ids(ctx, db, None)
    query = db.query(Location).filter(Location.is_active.is_(True))
    if allowed is not None:
        if not allowed:
            return []
        query = query.filter(Location.id.in_(allowed))
    return query.order_by(Location.name).all()


def _location_stats(db: Session, location: Location) -> Dict[str, int]:
    tz = location.timezone
    day_start, day_end = get_location_day_bounds(tz)
    base = (
        db.query(Visit)
        .filter(
            Visit.location_id == location.id,
            Visit.source == "self_registration",
        )
    )
    today = base.filter(Visit.created_at >= day_start, Visit.created_at < day_end).count()
    pending = base.filter(Visit.status == VisitStatus.PENDING_APPROVAL.value).count()
    approved = base.filter(
        Visit.status == VisitStatus.APPROVED.value,
        Visit.created_at >= day_start,
        Visit.created_at < day_end,
    ).count()
    rejected = base.filter(
        Visit.status == VisitStatus.REJECTED.value,
        Visit.created_at >= day_start,
        Visit.created_at < day_end,
    ).count()
    return {
        "today": today,
        "pending": pending,
        "approved": approved,
        "rejected": rejected,
    }


def _serialize_location(loc: Location, include_token: bool = False) -> Dict[str, Any]:
    token = loc.public_registration_token if include_token else None
    url = build_registration_public_url(token) if token else None
    return {
        "id": loc.id,
        "name": loc.name,
        "code": loc.code,
        "city": loc.city,
        "timezone": loc.timezone,
        "registration_enabled": loc.registration_enabled,
        "public_registration_token": token,
        "registration_url": url,
    }


def get_self_registration_qr_config(
    db: Session,
    ctx: AuthContext,
    location_id: Optional[int] = None,
) -> Dict[str, Any]:
    locations = _accessible_locations(db, ctx)
    if not locations:
        raise SelfRegistrationQrError("forbidden", "No accessible locations.", 403)

    selected: Optional[Location] = None
    if location_id is not None:
        if not can_access_location(ctx, location_id):
            raise SelfRegistrationQrError("forbidden", "You do not have access to this location.", 403)
        selected = db.query(Location).filter(Location.id == location_id, Location.is_active.is_(True)).first()
        if not selected:
            raise SelfRegistrationQrError("not_found", "Location not found.", 404)
    else:
        selected = locations[0]

    if not selected.public_registration_token:
        raise SelfRegistrationQrError(
            "registration_unavailable",
            "Registration link is not configured for this location.",
            503,
        )

    if not selected.registration_enabled:
        raise SelfRegistrationQrError(
            "registration_unavailable",
            "Self-registration is disabled for this location.",
            503,
        )

    registration_url = build_registration_public_url(selected.public_registration_token)
    stats = _location_stats(db, selected)

    return {
        "company_label": _company_label(),
        "app_name": settings.app_name,
        "locations": [_serialize_location(loc) for loc in locations],
        "location": _serialize_location(selected, include_token=True),
        "registration_url": registration_url,
        "is_permanent": True,
        "localhost_warning": is_localhost_public_url(registration_url),
        "stats": stats,
    }
