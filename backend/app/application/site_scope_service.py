"""Site/location scope filtering for admin queries."""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy.orm import Query, Session

from app.application.auth_service import AuthContext
from app.domain.enums import AdminRole
from app.domain.models import Location, Visit


def get_allowed_location_ids(ctx: AuthContext, db: Session, site_filter: Optional[int] = None) -> Optional[List[int]]:
    """
    Returns list of allowed location IDs, or None meaning all locations (global access).
    Empty list means no access.
    """
    if ctx.is_owner or ctx.role == AdminRole.GLOBAL_ADMIN:
        if site_filter is not None:
            return [site_filter]
        return None

    if ctx.role == AdminRole.HEAD_ADMIN:
        # Multi-site management: all active locations until advanced scope exists
        if site_filter is not None:
            return [site_filter]
        return None

    if ctx.role == AdminRole.SITE_ADMIN or ctx.role == AdminRole.SECURITY:
        allowed = ctx.location_ids
        if site_filter is not None:
            if site_filter not in allowed:
                return []
            return [site_filter]
        return allowed

    return []


def apply_location_scope(query: Query, ctx: AuthContext, db: Session, site_filter: Optional[int] = None) -> Query:
    allowed = get_allowed_location_ids(ctx, db, site_filter)
    if allowed is None:
        if site_filter is not None:
            return query.filter(Visit.location_id == site_filter)
        return query
    if not allowed:
        return query.filter(Visit.id == -1)  # no results
    return query.filter(Visit.location_id.in_(allowed))


def can_access_location(ctx: AuthContext, location_id: int) -> bool:
    if ctx.is_owner or ctx.role == AdminRole.GLOBAL_ADMIN:
        return True
    if ctx.role == AdminRole.HEAD_ADMIN:
        return True
    if ctx.role == AdminRole.SITE_ADMIN or ctx.role == AdminRole.SECURITY:
        return location_id in ctx.location_ids
    return False
