"""Watchlist entry administration."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.application.audit_service import AuditService
from app.application.auth_service import AuthContext
from app.application.identity_normalization import (
    normalize_company,
    normalize_email,
    normalize_mobile,
    normalize_person_name,
)
from app.application.site_scope_service import can_access_location, get_allowed_location_ids
from app.domain.enums import (
    Permission,
    WatchlistActionLevel,
    WatchlistEntryStatus,
    WatchlistReasonCode,
    WatchlistScopeType,
    role_has_permission,
)
from app.domain.models import Location, WatchlistEntry


class WatchlistError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _require_read(ctx: AuthContext) -> None:
    if not role_has_permission(ctx.role, Permission.WATCHLIST_READ):
        raise WatchlistError("forbidden", "Permission denied.", 403)


def _build_dict(entry: WatchlistEntry, db: Session) -> Dict[str, Any]:
    location = None
    if entry.location_id:
        location = db.query(Location).filter(Location.id == entry.location_id).first()
    return {
        "id": entry.id,
        "scope_type": entry.scope_type,
        "location_id": entry.location_id,
        "location_name": location.name if location else None,
        "full_name": entry.full_name,
        "mobile": entry.mobile,
        "email": entry.email,
        "company": entry.company,
        "reason_code": entry.reason_code,
        "reason_text": entry.reason_text,
        "action_level": entry.action_level,
        "status": entry.status,
        "valid_from": entry.valid_from.isoformat() if entry.valid_from else None,
        "valid_until": entry.valid_until.isoformat() if entry.valid_until else None,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
        "deactivated_at": entry.deactivated_at.isoformat() if entry.deactivated_at else None,
    }


def list_watchlist(
    db: Session,
    ctx: AuthContext,
    search: Optional[str] = None,
    scope: Optional[str] = None,
    location_id: Optional[int] = None,
    status: Optional[str] = None,
    action_level: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[List[Dict[str, Any]], int]:
    _require_read(ctx)
    query = db.query(WatchlistEntry)
    allowed = get_allowed_location_ids(ctx, db, location_id)
    if allowed is not None:
        if not allowed:
            query = query.filter(WatchlistEntry.id == -1)
        else:
            query = query.filter(
                (WatchlistEntry.scope_type == WatchlistScopeType.GLOBAL.value)
                | (WatchlistEntry.location_id.in_(allowed))
            )
    if scope:
        query = query.filter(WatchlistEntry.scope_type == scope.upper())
    if location_id:
        query = query.filter(
            (WatchlistEntry.scope_type == WatchlistScopeType.GLOBAL.value)
            | (WatchlistEntry.location_id == location_id)
        )
    if status:
        query = query.filter(WatchlistEntry.status == status.upper())
    if action_level:
        query = query.filter(WatchlistEntry.action_level == action_level.upper())
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            WatchlistEntry.full_name.ilike(term)
            | WatchlistEntry.normalized_name.ilike(term.lower())
            | WatchlistEntry.company.ilike(term)
            | WatchlistEntry.normalized_mobile.ilike(term)
            | WatchlistEntry.normalized_email.ilike(term)
        )
    total = query.count()
    rows = query.order_by(WatchlistEntry.created_at.desc()).offset(offset).limit(limit).all()
    return [_build_dict(r, db) for r in rows], total


def create_watchlist_entry(
    db: Session,
    ctx: AuthContext,
    scope_type: str,
    full_name: str,
    reason_code: str,
    action_level: str,
    valid_from: datetime,
    location_id: Optional[int] = None,
    mobile: Optional[str] = None,
    email: Optional[str] = None,
    company: Optional[str] = None,
    reason_text: Optional[str] = None,
    valid_until: Optional[datetime] = None,
) -> Dict[str, Any]:
    scope = WatchlistScopeType(scope_type)
    action = WatchlistActionLevel(action_level)
    try:
        reason = WatchlistReasonCode(reason_code)
    except ValueError:
        raise WatchlistError("invalid_reason", "Invalid watchlist reason.")
    if reason == WatchlistReasonCode.OTHER and not (reason_text and reason_text.strip()):
        raise WatchlistError("reason_required", "Reason text is required for Other.")

    if scope == WatchlistScopeType.GLOBAL:
        if not role_has_permission(ctx.role, Permission.WATCHLIST_CREATE):
            raise WatchlistError("forbidden", "Permission denied.", 403)
        location_id = None
    else:
        if not role_has_permission(ctx.role, Permission.WATCHLIST_CREATE_LOCATION):
            raise WatchlistError("forbidden", "Permission denied.", 403)
        if not location_id or not can_access_location(ctx, location_id):
            raise WatchlistError("forbidden", "You do not have access to this location.", 403)

    norm_mobile = normalize_mobile(mobile)
    norm_email = normalize_email(email)
    if not norm_mobile and not norm_email and not full_name.strip():
        raise WatchlistError("invalid_entry", "Name and at least one identifier are required.")

    entry = WatchlistEntry(
        scope_type=scope.value,
        location_id=location_id,
        full_name=full_name.strip(),
        normalized_name=normalize_person_name(full_name) or "",
        mobile=mobile,
        normalized_mobile=norm_mobile,
        email=email,
        normalized_email=norm_email,
        company=company,
        normalized_company=normalize_company(company),
        reason_code=reason.value,
        reason_text=reason_text,
        action_level=action.value,
        status=WatchlistEntryStatus.ACTIVE.value,
        valid_from=valid_from,
        valid_until=valid_until,
        created_by_user_id=ctx.user_id,
        updated_by_user_id=ctx.user_id,
    )
    db.add(entry)
    db.flush()
    AuditService(db).record(
        action="WATCHLIST_ENTRY_CREATED",
        entity_type="watchlist_entry",
        entity_id=str(entry.id),
        actor_id=ctx.user_id,
        actor_email=ctx.email,
        location_id=location_id,
        after_value={"scope": scope.value, "action_level": action.value},
    )
    db.commit()
    return _build_dict(entry, db)


def update_watchlist_entry(
    db: Session,
    ctx: AuthContext,
    entry_id: int,
    action_level: Optional[str] = None,
    reason_text: Optional[str] = None,
    valid_until: Optional[datetime] = None,
) -> Dict[str, Any]:
    if not role_has_permission(ctx.role, Permission.WATCHLIST_UPDATE):
        raise WatchlistError("forbidden", "Permission denied.", 403)
    entry = db.query(WatchlistEntry).filter(WatchlistEntry.id == entry_id).first()
    if not entry:
        raise WatchlistError("not_found", "Watchlist entry not found.", 404)
    if entry.scope_type == WatchlistScopeType.LOCATION.value and entry.location_id:
        if not can_access_location(ctx, entry.location_id):
            raise WatchlistError("forbidden", "Permission denied.", 403)
    before = {"action_level": entry.action_level, "reason_text": entry.reason_text}
    if action_level:
        entry.action_level = WatchlistActionLevel(action_level).value
    if reason_text is not None:
        entry.reason_text = reason_text
    if valid_until is not None:
        entry.valid_until = valid_until
    entry.updated_by_user_id = ctx.user_id
    AuditService(db).record(
        action="WATCHLIST_ENTRY_UPDATED",
        entity_type="watchlist_entry",
        entity_id=str(entry.id),
        actor_id=ctx.user_id,
        actor_email=ctx.email,
        location_id=entry.location_id,
        before_value=before,
        after_value={"action_level": entry.action_level, "reason_text": entry.reason_text},
    )
    db.commit()
    return _build_dict(entry, db)


def deactivate_watchlist_entry(db: Session, ctx: AuthContext, entry_id: int) -> Dict[str, Any]:
    if not role_has_permission(ctx.role, Permission.WATCHLIST_DEACTIVATE):
        raise WatchlistError("forbidden", "Permission denied.", 403)
    entry = db.query(WatchlistEntry).filter(WatchlistEntry.id == entry_id).first()
    if not entry:
        raise WatchlistError("not_found", "Watchlist entry not found.", 404)
    if entry.scope_type == WatchlistScopeType.LOCATION.value and entry.location_id:
        if not can_access_location(ctx, entry.location_id):
            raise WatchlistError("forbidden", "Permission denied.", 403)
    entry.status = WatchlistEntryStatus.INACTIVE.value
    entry.deactivated_at = datetime.now(timezone.utc)
    entry.updated_by_user_id = ctx.user_id
    AuditService(db).record(
        action="WATCHLIST_ENTRY_DEACTIVATED",
        entity_type="watchlist_entry",
        entity_id=str(entry.id),
        actor_id=ctx.user_id,
        actor_email=ctx.email,
        location_id=entry.location_id,
    )
    db.commit()
    return _build_dict(entry, db)


def get_watchlist_entry(db: Session, ctx: AuthContext, entry_id: int) -> Dict[str, Any]:
    _require_read(ctx)
    entry = db.query(WatchlistEntry).filter(WatchlistEntry.id == entry_id).first()
    if not entry:
        raise WatchlistError("not_found", "Watchlist entry not found.", 404)
    if entry.scope_type == WatchlistScopeType.LOCATION.value and entry.location_id:
        if not can_access_location(ctx, entry.location_id):
            raise WatchlistError("forbidden", "Permission denied.", 403)
    return _build_dict(entry, db)
