"""Compliance requirement configuration."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.application.audit_service import AuditService
from app.application.auth_service import AuthContext
from app.application.site_scope_service import can_access_location
from app.domain.enums import ComplianceDocumentOwnerType, ComplianceScopeType, Permission, role_has_permission
from app.domain.models import ComplianceRequirement, Location, VisitorType


class ComplianceRequirementError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _require_manage(ctx: AuthContext) -> None:
    if not role_has_permission(ctx.role, Permission.COMPLIANCE_MANAGE_REQUIREMENTS):
        raise ComplianceRequirementError("forbidden", "Permission denied.", 403)


def _require_read(ctx: AuthContext) -> None:
    if not role_has_permission(ctx.role, Permission.COMPLIANCE_READ):
        raise ComplianceRequirementError("forbidden", "Permission denied.", 403)


def _slug_code(name: str) -> str:
    base = re.sub(r"[^A-Za-z0-9]+", "_", name.strip().upper()).strip("_")
    return base[:48] or "REQUIREMENT"


def _build_dict(db: Session, req: ComplianceRequirement) -> Dict[str, Any]:
    visitor_type_name = None
    if req.visitor_type_id:
        vt = db.query(VisitorType).filter(VisitorType.id == req.visitor_type_id).first()
        visitor_type_name = vt.name if vt else None
    location_name = None
    location_code = None
    if req.location_id:
        loc = db.query(Location).filter(Location.id == req.location_id).first()
        if loc:
            location_name = loc.name
            location_code = loc.code
    return {
        "id": req.id,
        "name": req.name,
        "code": req.code,
        "description": req.description,
        "visitor_type_id": req.visitor_type_id,
        "visitor_type_name": visitor_type_name,
        "scope_type": req.scope_type,
        "location_id": req.location_id,
        "location_name": location_name,
        "location_code": location_code,
        "document_owner_type": req.document_owner_type,
        "document_required": req.document_required,
        "validity_required": req.validity_required,
        "safety_acknowledgement_required": req.safety_acknowledgement_required,
        "is_mandatory": req.is_mandatory,
        "is_active": req.is_active,
        "expiry_warning_days": req.expiry_warning_days,
        "created_at": req.created_at.isoformat() if req.created_at else None,
        "updated_at": req.updated_at.isoformat() if req.updated_at else None,
    }


def list_requirements_admin(db: Session, ctx: AuthContext, include_inactive: bool = True) -> List[Dict[str, Any]]:
    _require_manage(ctx)
    query = db.query(ComplianceRequirement)
    if not include_inactive:
        query = query.filter(ComplianceRequirement.is_active.is_(True))
    rows = query.order_by(ComplianceRequirement.name).all()
    return [_build_dict(db, r) for r in rows]


def create_requirement(
    db: Session,
    ctx: AuthContext,
    name: str,
    description: Optional[str] = None,
    visitor_type_id: Optional[int] = None,
    scope_type: str = ComplianceScopeType.GLOBAL.value,
    location_id: Optional[int] = None,
    document_owner_type: str = ComplianceDocumentOwnerType.VISITOR.value,
    document_required: bool = True,
    validity_required: bool = True,
    safety_acknowledgement_required: bool = False,
    is_mandatory: bool = True,
    expiry_warning_days: int = 30,
    code: Optional[str] = None,
) -> Dict[str, Any]:
    _require_manage(ctx)
    if not name or not name.strip():
        raise ComplianceRequirementError("invalid_name", "Requirement name is required.")
    scope = scope_type.upper()
    if scope == ComplianceScopeType.LOCATION.value:
        if not location_id:
            raise ComplianceRequirementError("location_required", "Location is required for location-scoped requirements.")
        if not can_access_location(ctx, location_id):
            raise ComplianceRequirementError("forbidden", "You do not have access to this location.", 403)
    elif scope != ComplianceScopeType.GLOBAL.value:
        raise ComplianceRequirementError("invalid_scope", "Scope must be GLOBAL or LOCATION.")
    owner = document_owner_type.upper()
    if owner not in (ComplianceDocumentOwnerType.COMPANY.value, ComplianceDocumentOwnerType.VISITOR.value):
        raise ComplianceRequirementError("invalid_owner", "Invalid document owner type.")
    req_code = (code or _slug_code(name)).upper()
    existing = db.query(ComplianceRequirement).filter(ComplianceRequirement.code == req_code).first()
    if existing:
        raise ComplianceRequirementError("duplicate_code", "A requirement with this code already exists.")
    req = ComplianceRequirement(
        name=name.strip(),
        code=req_code,
        description=description,
        visitor_type_id=visitor_type_id,
        scope_type=scope,
        location_id=location_id if scope == ComplianceScopeType.LOCATION.value else None,
        document_owner_type=owner,
        document_required=document_required,
        validity_required=validity_required,
        safety_acknowledgement_required=safety_acknowledgement_required,
        is_mandatory=is_mandatory,
        is_active=True,
        expiry_warning_days=max(1, min(expiry_warning_days, 365)),
    )
    db.add(req)
    db.flush()
    AuditService(db).record(
        action="COMPLIANCE_REQUIREMENT_CREATED",
        entity_type="compliance_requirement",
        entity_id=str(req.id),
        actor_id=ctx.user_id,
        actor_email=ctx.email,
        after_value={"code": req.code, "name": req.name},
    )
    db.commit()
    return _build_dict(db, req)


def update_requirement(
    db: Session,
    ctx: AuthContext,
    requirement_id: int,
    name: Optional[str] = None,
    description: Optional[str] = None,
    is_mandatory: Optional[bool] = None,
    validity_required: Optional[bool] = None,
    expiry_warning_days: Optional[int] = None,
    document_required: Optional[bool] = None,
) -> Dict[str, Any]:
    _require_manage(ctx)
    req = db.query(ComplianceRequirement).filter(ComplianceRequirement.id == requirement_id).first()
    if not req:
        raise ComplianceRequirementError("not_found", "Requirement not found.", 404)
    if name is not None:
        req.name = name.strip()
    if description is not None:
        req.description = description
    if is_mandatory is not None:
        req.is_mandatory = is_mandatory
    if validity_required is not None:
        req.validity_required = validity_required
    if document_required is not None:
        req.document_required = document_required
    if expiry_warning_days is not None:
        req.expiry_warning_days = max(1, min(expiry_warning_days, 365))
    AuditService(db).record(
        action="COMPLIANCE_REQUIREMENT_UPDATED",
        entity_type="compliance_requirement",
        entity_id=str(req.id),
        actor_id=ctx.user_id,
        actor_email=ctx.email,
    )
    db.commit()
    return _build_dict(db, req)


def deactivate_requirement(db: Session, ctx: AuthContext, requirement_id: int) -> Dict[str, Any]:
    _require_manage(ctx)
    req = db.query(ComplianceRequirement).filter(ComplianceRequirement.id == requirement_id).first()
    if not req:
        raise ComplianceRequirementError("not_found", "Requirement not found.", 404)
    req.is_active = False
    AuditService(db).record(
        action="COMPLIANCE_REQUIREMENT_DEACTIVATED",
        entity_type="compliance_requirement",
        entity_id=str(req.id),
        actor_id=ctx.user_id,
        actor_email=ctx.email,
    )
    db.commit()
    return _build_dict(db, req)
