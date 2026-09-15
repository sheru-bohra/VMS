"""Access profile and location configuration management."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set

from sqlalchemy.orm import Session

from app.application.audit_service import AuditService
from app.application.auth_service import AuthContext
from app.application.site_scope_service import can_access_location
from app.domain.enums import Permission, role_has_permission
from app.domain.models import (
    AccessProfile,
    BadgePrinter,
    Location,
    LocationAccessConfiguration,
    VisitorType,
    VisitorTypeAccessProfile,
)


class AccessConfigError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


_CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f]")
_MAX_REF_LEN = 128


def _require_config_read(ctx: AuthContext) -> None:
    if not role_has_permission(ctx.role, Permission.ACCESS_CONFIG_READ):
        raise AccessConfigError("forbidden", "Permission denied.", 403)


def _require_config_manage(ctx: AuthContext) -> None:
    if not role_has_permission(ctx.role, Permission.ACCESS_CONFIG_MANAGE):
        raise AccessConfigError("forbidden", "Permission denied.", 403)


def _require_printer_manage(ctx: AuthContext) -> None:
    if not role_has_permission(ctx.role, Permission.BADGE_PRINTER_CONFIG_MANAGE):
        raise AccessConfigError("forbidden", "Permission denied.", 403)


def _validate_external_ref(value: str, field_label: str) -> str:
    ref = value.strip()
    if not ref:
        raise AccessConfigError("invalid_ref", f"{field_label} is required.", 400)
    if len(ref) > _MAX_REF_LEN:
        raise AccessConfigError("invalid_ref", f"{field_label} is too long.", 400)
    if _CONTROL_CHAR_RE.search(ref):
        raise AccessConfigError("invalid_ref", f"{field_label} contains invalid characters.", 400)
    return ref


def _profile_dict(p: AccessProfile) -> Dict[str, Any]:
    return {
        "id": p.id,
        "location_id": p.location_id,
        "name": p.name,
        "description": p.description,
        "provider_external_profile_ref": p.provider_external_profile_ref,
        "is_active": p.is_active,
    }


def _mapping_dict(db: Session, m: VisitorTypeAccessProfile) -> Dict[str, Any]:
    vt = db.query(VisitorType).filter(VisitorType.id == m.visitor_type_id).first()
    ap = db.query(AccessProfile).filter(AccessProfile.id == m.access_profile_id).first()
    return {
        "id": m.id,
        "location_id": m.location_id,
        "visitor_type_id": m.visitor_type_id,
        "visitor_type_name": vt.name if vt else None,
        "access_profile_id": m.access_profile_id,
        "access_profile_name": ap.name if ap else None,
        "is_active": m.is_active,
    }


def _location_config_dict(db: Session, cfg: LocationAccessConfiguration) -> Dict[str, Any]:
    loc = db.query(Location).filter(Location.id == cfg.location_id).first()
    return {
        "id": cfg.id,
        "location_id": cfg.location_id,
        "location_name": loc.name if loc else None,
        "access_control_enabled": cfg.access_control_enabled,
        "provider_key": cfg.provider_key,
        "default_access_profile_id": cfg.default_access_profile_id,
        "credential_grace_minutes": cfg.credential_grace_minutes,
        "max_credential_duration_minutes": cfg.max_credential_duration_minutes,
        "is_active": cfg.is_active,
    }


def _validate_location_access_enable(db: Session, cfg: LocationAccessConfiguration) -> None:
    has_mapping = (
        db.query(VisitorTypeAccessProfile)
        .filter(
            VisitorTypeAccessProfile.location_id == cfg.location_id,
            VisitorTypeAccessProfile.is_active.is_(True),
        )
        .count()
        > 0
    )
    has_default = False
    if cfg.default_access_profile_id:
        default = db.query(AccessProfile).filter(
            AccessProfile.id == cfg.default_access_profile_id,
            AccessProfile.location_id == cfg.location_id,
            AccessProfile.is_active.is_(True),
        ).first()
        has_default = default is not None
    if not has_mapping and not has_default:
        raise AccessConfigError(
            "access_config_incomplete",
            "Enable access control requires visitor type mappings or an active default access profile.",
            400,
        )


def list_location_configs(db: Session, ctx: AuthContext) -> List[Dict[str, Any]]:
    _require_config_read(ctx)
    configs = db.query(LocationAccessConfiguration).all()
    result = []
    for cfg in configs:
        if not can_access_location(ctx, cfg.location_id):
            continue
        result.append(_location_config_dict(db, cfg))
    return result


def update_location_config(
    db: Session,
    ctx: AuthContext,
    location_id: int,
    **fields: Any,
) -> Dict[str, Any]:
    _require_config_manage(ctx)
    if not can_access_location(ctx, location_id):
        raise AccessConfigError("forbidden", "Location access denied.", 403)
    cfg = db.query(LocationAccessConfiguration).filter(LocationAccessConfiguration.location_id == location_id).first()
    if not cfg:
        cfg = LocationAccessConfiguration(location_id=location_id)
        db.add(cfg)
        db.flush()

    before: Dict[str, Any] = {
        "access_control_enabled": cfg.access_control_enabled,
        "default_access_profile_id": cfg.default_access_profile_id,
        "credential_grace_minutes": cfg.credential_grace_minutes,
        "max_credential_duration_minutes": cfg.max_credential_duration_minutes,
    }
    changed: Set[str] = set()

    allowed = {
        "access_control_enabled", "provider_key", "default_access_profile_id",
        "credential_grace_minutes", "max_credential_duration_minutes", "is_active",
    }
    for key, val in fields.items():
        if key not in allowed or val is None:
            continue
        if key == "credential_grace_minutes" and int(val) < 0:
            raise AccessConfigError("invalid_grace", "Grace minutes must be >= 0.", 400)
        if key == "max_credential_duration_minutes" and int(val) <= 0:
            raise AccessConfigError("invalid_max_duration", "Max credential duration must be > 0.", 400)
        if key == "default_access_profile_id":
            profile = db.query(AccessProfile).filter(AccessProfile.id == val).first()
            if not profile or profile.location_id != location_id:
                raise AccessConfigError("invalid_default_profile", "Default profile must belong to this location.", 400)
            if not profile.is_active:
                raise AccessConfigError("inactive_default_profile", "Default profile must be active.", 400)
        if getattr(cfg, key) != val:
            changed.add(key)
        setattr(cfg, key, val)

    if cfg.access_control_enabled:
        _validate_location_access_enable(db, cfg)

    db.flush()
    if changed:
        AuditService(db).record(
            action="LOCATION_ACCESS_CONFIGURATION_UPDATED",
            entity_type="location_access_configuration",
            entity_id=str(cfg.id),
            actor_id=ctx.user_id,
            actor_email=ctx.email,
            location_id=location_id,
            before_value={k: before[k] for k in changed if k in before},
            after_value={k: getattr(cfg, k) for k in changed},
        )
    return _location_config_dict(db, cfg)


def list_profiles(db: Session, ctx: AuthContext, location_id: Optional[int] = None) -> List[Dict[str, Any]]:
    _require_config_read(ctx)
    q = db.query(AccessProfile)
    if location_id:
        q = q.filter(AccessProfile.location_id == location_id)
    rows = q.order_by(AccessProfile.name).all()
    return [_profile_dict(p) for p in rows if can_access_location(ctx, p.location_id)]


def get_profile(db: Session, ctx: AuthContext, profile_id: int) -> Dict[str, Any]:
    _require_config_read(ctx)
    profile = db.query(AccessProfile).filter(AccessProfile.id == profile_id).first()
    if not profile:
        raise AccessConfigError("not_found", "Profile not found.", 404)
    if not can_access_location(ctx, profile.location_id):
        raise AccessConfigError("forbidden", "Location access denied.", 403)
    return _profile_dict(profile)


def create_profile(
    db: Session,
    ctx: AuthContext,
    location_id: int,
    name: str,
    provider_external_profile_ref: str,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    _require_config_manage(ctx)
    if not can_access_location(ctx, location_id):
        raise AccessConfigError("forbidden", "Location access denied.", 403)
    clean_name = name.strip()
    if not clean_name:
        raise AccessConfigError("invalid_name", "Profile name is required.", 400)
    ref = _validate_external_ref(provider_external_profile_ref, "Provider profile reference")
    dup = (
        db.query(AccessProfile)
        .filter(
            AccessProfile.location_id == location_id,
            AccessProfile.name == clean_name,
            AccessProfile.is_active.is_(True),
        )
        .first()
    )
    if dup:
        raise AccessConfigError("duplicate_profile", "An active profile with this name already exists.", 409)
    profile = AccessProfile(
        location_id=location_id,
        name=clean_name,
        description=description.strip() if description else None,
        provider_external_profile_ref=ref,
        is_active=True,
    )
    db.add(profile)
    db.flush()
    AuditService(db).record(
        action="ACCESS_PROFILE_CREATED",
        entity_type="access_profile",
        entity_id=str(profile.id),
        actor_id=ctx.user_id,
        actor_email=ctx.email,
        location_id=location_id,
        after_value={"name": clean_name},
    )
    return _profile_dict(profile)


def update_profile(
    db: Session,
    ctx: AuthContext,
    profile_id: int,
    **fields: Any,
) -> Dict[str, Any]:
    _require_config_manage(ctx)
    profile = db.query(AccessProfile).filter(AccessProfile.id == profile_id).first()
    if not profile:
        raise AccessConfigError("not_found", "Profile not found.", 404)
    if not can_access_location(ctx, profile.location_id):
        raise AccessConfigError("forbidden", "Location access denied.", 403)

    before: Dict[str, Any] = {}
    changed: Set[str] = set()
    allowed = {"name", "description", "provider_external_profile_ref"}
    for key, val in fields.items():
        if key not in allowed or val is None:
            continue
        if key == "name":
            val = val.strip()
            if not val:
                raise AccessConfigError("invalid_name", "Profile name is required.", 400)
        if key == "provider_external_profile_ref":
            val = _validate_external_ref(str(val), "Provider profile reference")
        if getattr(profile, key) != val:
            before[key] = getattr(profile, key)
            changed.add(key)
            setattr(profile, key, val)

    db.flush()
    if changed:
        AuditService(db).record(
            action="ACCESS_PROFILE_UPDATED",
            entity_type="access_profile",
            entity_id=str(profile.id),
            actor_id=ctx.user_id,
            actor_email=ctx.email,
            location_id=profile.location_id,
            before_value=before,
            after_value={k: getattr(profile, k) for k in changed},
        )
    return _profile_dict(profile)


def deactivate_profile(db: Session, ctx: AuthContext, profile_id: int) -> Dict[str, Any]:
    _require_config_manage(ctx)
    profile = db.query(AccessProfile).filter(AccessProfile.id == profile_id).first()
    if not profile:
        raise AccessConfigError("not_found", "Profile not found.", 404)
    if not can_access_location(ctx, profile.location_id):
        raise AccessConfigError("forbidden", "Location access denied.", 403)
    profile.is_active = False
    AuditService(db).record(
        action="ACCESS_PROFILE_DEACTIVATED",
        entity_type="access_profile",
        entity_id=str(profile.id),
        actor_id=ctx.user_id,
        actor_email=ctx.email,
        location_id=profile.location_id,
    )
    return {"id": profile.id, "is_active": False}


def list_profile_mappings(db: Session, ctx: AuthContext, location_id: Optional[int] = None) -> List[Dict[str, Any]]:
    _require_config_read(ctx)
    q = db.query(VisitorTypeAccessProfile)
    if location_id:
        q = q.filter(VisitorTypeAccessProfile.location_id == location_id)
    return [_mapping_dict(db, m) for m in q.all() if can_access_location(ctx, m.location_id)]


def create_profile_mapping(
    db: Session,
    ctx: AuthContext,
    location_id: int,
    visitor_type_id: int,
    access_profile_id: int,
) -> Dict[str, Any]:
    _require_config_manage(ctx)
    if not can_access_location(ctx, location_id):
        raise AccessConfigError("forbidden", "Location access denied.", 403)
    profile = db.query(AccessProfile).filter(AccessProfile.id == access_profile_id).first()
    if not profile or profile.location_id != location_id or not profile.is_active:
        raise AccessConfigError("invalid_profile", "Access profile not found for this location.", 400)
    existing = (
        db.query(VisitorTypeAccessProfile)
        .filter(
            VisitorTypeAccessProfile.location_id == location_id,
            VisitorTypeAccessProfile.visitor_type_id == visitor_type_id,
            VisitorTypeAccessProfile.is_active.is_(True),
        )
        .first()
    )
    if existing and existing.access_profile_id != access_profile_id:
        raise AccessConfigError(
            "mapping_conflict",
            "An active mapping already exists for this visitor type at this location.",
            409,
        )
    if existing:
        return _mapping_dict(db, existing)
    mapping = VisitorTypeAccessProfile(
        location_id=location_id,
        visitor_type_id=visitor_type_id,
        access_profile_id=access_profile_id,
        is_active=True,
    )
    db.add(mapping)
    db.flush()
    AuditService(db).record(
        action="ACCESS_PROFILE_MAPPING_CREATED",
        entity_type="visitor_type_access_profile",
        entity_id=str(mapping.id),
        actor_id=ctx.user_id,
        actor_email=ctx.email,
        location_id=location_id,
        after_value={"visitor_type_id": visitor_type_id, "access_profile_id": access_profile_id},
    )
    return _mapping_dict(db, mapping)


def update_profile_mapping(
    db: Session,
    ctx: AuthContext,
    mapping_id: int,
    access_profile_id: int,
) -> Dict[str, Any]:
    _require_config_manage(ctx)
    mapping = db.query(VisitorTypeAccessProfile).filter(VisitorTypeAccessProfile.id == mapping_id).first()
    if not mapping:
        raise AccessConfigError("not_found", "Mapping not found.", 404)
    if not can_access_location(ctx, mapping.location_id):
        raise AccessConfigError("forbidden", "Location access denied.", 403)
    profile = db.query(AccessProfile).filter(AccessProfile.id == access_profile_id).first()
    if not profile or profile.location_id != mapping.location_id or not profile.is_active:
        raise AccessConfigError("invalid_profile", "Access profile not found for this location.", 400)
    before_profile_id = mapping.access_profile_id
    mapping.access_profile_id = access_profile_id
    mapping.is_active = True
    db.flush()
    AuditService(db).record(
        action="ACCESS_PROFILE_MAPPING_UPDATED",
        entity_type="visitor_type_access_profile",
        entity_id=str(mapping.id),
        actor_id=ctx.user_id,
        actor_email=ctx.email,
        location_id=mapping.location_id,
        before_value={"access_profile_id": before_profile_id},
        after_value={"access_profile_id": access_profile_id},
    )
    return _mapping_dict(db, mapping)


def deactivate_profile_mapping(db: Session, ctx: AuthContext, mapping_id: int) -> Dict[str, Any]:
    _require_config_manage(ctx)
    mapping = db.query(VisitorTypeAccessProfile).filter(VisitorTypeAccessProfile.id == mapping_id).first()
    if not mapping:
        raise AccessConfigError("not_found", "Mapping not found.", 404)
    if not can_access_location(ctx, mapping.location_id):
        raise AccessConfigError("forbidden", "Location access denied.", 403)
    mapping.is_active = False
    AuditService(db).record(
        action="ACCESS_PROFILE_MAPPING_DEACTIVATED",
        entity_type="visitor_type_access_profile",
        entity_id=str(mapping.id),
        actor_id=ctx.user_id,
        actor_email=ctx.email,
        location_id=mapping.location_id,
    )
    return {"id": mapping.id, "is_active": False}


def list_printers(db: Session, ctx: AuthContext, location_id: Optional[int] = None) -> List[Dict[str, Any]]:
    _require_config_read(ctx)
    q = db.query(BadgePrinter)
    if location_id:
        q = q.filter(BadgePrinter.location_id == location_id)
    return [
        {
            "id": p.id,
            "location_id": p.location_id,
            "name": p.name,
            "provider_key": p.provider_key,
            "provider_external_printer_ref": p.provider_external_printer_ref,
            "is_default": p.is_default,
            "is_active": p.is_active,
        }
        for p in q.all()
        if can_access_location(ctx, p.location_id)
    ]


def get_printer(db: Session, ctx: AuthContext, printer_id: int) -> Dict[str, Any]:
    _require_config_read(ctx)
    printer = db.query(BadgePrinter).filter(BadgePrinter.id == printer_id).first()
    if not printer:
        raise AccessConfigError("not_found", "Printer not found.", 404)
    if not can_access_location(ctx, printer.location_id):
        raise AccessConfigError("forbidden", "Location access denied.", 403)
    return {
        "id": printer.id,
        "location_id": printer.location_id,
        "name": printer.name,
        "provider_key": printer.provider_key,
        "provider_external_printer_ref": printer.provider_external_printer_ref,
        "is_default": printer.is_default,
        "is_active": printer.is_active,
    }


def create_printer(
    db: Session,
    ctx: AuthContext,
    location_id: int,
    name: str,
    provider_key: str,
    provider_external_printer_ref: str,
    is_default: bool = False,
) -> Dict[str, Any]:
    _require_printer_manage(ctx)
    if not can_access_location(ctx, location_id):
        raise AccessConfigError("forbidden", "Location access denied.", 403)
    clean_name = name.strip()
    if not clean_name:
        raise AccessConfigError("invalid_name", "Printer name is required.", 400)
    ref = _validate_external_ref(provider_external_printer_ref, "Provider printer reference")
    if is_default:
        db.query(BadgePrinter).filter(
            BadgePrinter.location_id == location_id,
            BadgePrinter.is_default.is_(True),
        ).update({"is_default": False})
    printer = BadgePrinter(
        location_id=location_id,
        name=clean_name,
        provider_key=provider_key.strip(),
        provider_external_printer_ref=ref,
        is_default=is_default,
        is_active=True,
    )
    db.add(printer)
    db.flush()
    AuditService(db).record(
        action="BADGE_PRINTER_CREATED",
        entity_type="badge_printer",
        entity_id=str(printer.id),
        actor_id=ctx.user_id,
        actor_email=ctx.email,
        location_id=location_id,
    )
    return get_printer(db, ctx, printer.id)


def update_printer(
    db: Session,
    ctx: AuthContext,
    printer_id: int,
    **fields: Any,
) -> Dict[str, Any]:
    _require_printer_manage(ctx)
    printer = db.query(BadgePrinter).filter(BadgePrinter.id == printer_id).first()
    if not printer:
        raise AccessConfigError("not_found", "Printer not found.", 404)
    if not can_access_location(ctx, printer.location_id):
        raise AccessConfigError("forbidden", "Location access denied.", 403)

    before: Dict[str, Any] = {}
    changed: Set[str] = set()
    allowed = {"name", "provider_external_printer_ref", "is_active", "is_default"}
    for key, val in fields.items():
        if key not in allowed or val is None:
            continue
        if key == "name":
            val = val.strip()
            if not val:
                raise AccessConfigError("invalid_name", "Printer name is required.", 400)
        if key == "provider_external_printer_ref":
            val = _validate_external_ref(str(val), "Provider printer reference")
        if key == "is_default" and val:
            db.query(BadgePrinter).filter(
                BadgePrinter.location_id == printer.location_id,
                BadgePrinter.is_default.is_(True),
                BadgePrinter.id != printer.id,
            ).update({"is_default": False})
        if getattr(printer, key) != val:
            before[key] = getattr(printer, key)
            changed.add(key)
            setattr(printer, key, val)

    if printer.is_active and printer.is_default:
        db.query(BadgePrinter).filter(
            BadgePrinter.location_id == printer.location_id,
            BadgePrinter.is_default.is_(True),
            BadgePrinter.id != printer.id,
        ).update({"is_default": False})
        printer.is_default = True

    db.flush()
    if changed:
        AuditService(db).record(
            action="BADGE_PRINTER_UPDATED",
            entity_type="badge_printer",
            entity_id=str(printer.id),
            actor_id=ctx.user_id,
            actor_email=ctx.email,
            location_id=printer.location_id,
            before_value=before,
            after_value={k: getattr(printer, k) for k in changed},
        )
    return get_printer(db, ctx, printer.id)


def set_default_printer(db: Session, ctx: AuthContext, printer_id: int) -> Dict[str, Any]:
    _require_printer_manage(ctx)
    printer = db.query(BadgePrinter).filter(BadgePrinter.id == printer_id).first()
    if not printer:
        raise AccessConfigError("not_found", "Printer not found.", 404)
    if not can_access_location(ctx, printer.location_id):
        raise AccessConfigError("forbidden", "Location access denied.", 403)
    if not printer.is_active:
        raise AccessConfigError("inactive_printer", "Cannot set inactive printer as default.", 400)
    db.query(BadgePrinter).filter(
        BadgePrinter.location_id == printer.location_id,
        BadgePrinter.is_default.is_(True),
    ).update({"is_default": False})
    printer.is_default = True
    db.flush()
    AuditService(db).record(
        action="BADGE_PRINTER_UPDATED",
        entity_type="badge_printer",
        entity_id=str(printer.id),
        actor_id=ctx.user_id,
        actor_email=ctx.email,
        location_id=printer.location_id,
        after_value={"is_default": True},
    )
    return {"id": printer.id, "is_default": True}


def deactivate_printer(db: Session, ctx: AuthContext, printer_id: int) -> Dict[str, Any]:
    _require_printer_manage(ctx)
    printer = db.query(BadgePrinter).filter(BadgePrinter.id == printer_id).first()
    if not printer:
        raise AccessConfigError("not_found", "Printer not found.", 404)
    if not can_access_location(ctx, printer.location_id):
        raise AccessConfigError("forbidden", "Location access denied.", 403)
    printer.is_active = False
    printer.is_default = False
    AuditService(db).record(
        action="BADGE_PRINTER_DEACTIVATED",
        entity_type="badge_printer",
        entity_id=str(printer.id),
        actor_id=ctx.user_id,
        actor_email=ctx.email,
        location_id=printer.location_id,
    )
    return {"id": printer.id, "is_active": False}
