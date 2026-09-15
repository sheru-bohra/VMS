"""Vendor company administration."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.application.audit_service import AuditService
from app.application.auth_service import AuthContext
from app.application.compliance_document_service import list_documents_for_owner
from app.application.compliance_service import find_duplicate_vendor_companies
from app.application.identity_normalization import normalize_company
from app.application.site_scope_service import can_access_location, get_allowed_location_ids
from app.domain.enums import Permission, role_has_permission
from app.domain.models import Location, VendorCompany, VendorCompanyLocation, VendorVisitorProfile, Visitor, ComplianceRequirement


class VendorCompanyError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _require_manage(ctx: AuthContext) -> None:
    if not role_has_permission(ctx.role, Permission.VENDOR_COMPANY_MANAGE):
        raise VendorCompanyError("forbidden", "Permission denied.", 403)


def _require_read(ctx: AuthContext) -> None:
    if not role_has_permission(ctx.role, Permission.VENDOR_COMPANY_READ):
        raise VendorCompanyError("forbidden", "Permission denied.", 403)


def _build_company_dict(db: Session, company: VendorCompany) -> Dict[str, Any]:
    locations = (
        db.query(VendorCompanyLocation)
        .filter(VendorCompanyLocation.vendor_company_id == company.id, VendorCompanyLocation.is_active.is_(True))
        .all()
    )
    loc_names = []
    for vl in locations:
        loc = db.query(Location).filter(Location.id == vl.location_id).first()
        if loc:
            loc_names.append({"id": loc.id, "name": loc.name, "code": loc.code})
    return {
        "id": company.id,
        "name": company.name,
        "code": company.code,
        "primary_contact_name": company.primary_contact_name,
        "primary_contact_email": company.primary_contact_email,
        "primary_contact_mobile": company.primary_contact_mobile,
        "is_active": company.is_active,
        "locations": loc_names,
        "created_at": company.created_at.isoformat() if company.created_at else None,
    }


def list_vendor_companies(
    db: Session,
    ctx: AuthContext,
    search: Optional[str] = None,
    location_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[List[Dict[str, Any]], int]:
    _require_read(ctx)
    query = db.query(VendorCompany)
    allowed = get_allowed_location_ids(ctx, db, location_id)
    if allowed is not None:
        if not allowed:
            query = query.filter(VendorCompany.id == -1)
        else:
            query = query.join(VendorCompanyLocation).filter(
                VendorCompanyLocation.location_id.in_(allowed),
                VendorCompanyLocation.is_active.is_(True),
            ).distinct()
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            VendorCompany.name.ilike(term) | VendorCompany.normalized_name.ilike(term.lower())
        )
    total = query.count()
    rows = query.order_by(VendorCompany.name).offset(offset).limit(limit).all()
    return [_build_company_dict(db, r) for r in rows], total


def create_vendor_company(
    db: Session,
    ctx: AuthContext,
    name: str,
    location_ids: List[int],
    code: Optional[str] = None,
    primary_contact_name: Optional[str] = None,
    primary_contact_email: Optional[str] = None,
    primary_contact_mobile: Optional[str] = None,
) -> Dict[str, Any]:
    _require_manage(ctx)
    if not name or not name.strip():
        raise VendorCompanyError("invalid_name", "Company name is required.")
    if not location_ids:
        raise VendorCompanyError("location_required", "At least one location assignment is required.")
    for loc_id in location_ids:
        if not can_access_location(ctx, loc_id):
            raise VendorCompanyError("forbidden", "You do not have access to one or more locations.", 403)
    dupes = find_duplicate_vendor_companies(db, name)
    company = VendorCompany(
        name=name.strip(),
        normalized_name=normalize_company(name) or name.strip().casefold(),
        code=code,
        primary_contact_name=primary_contact_name,
        primary_contact_email=primary_contact_email,
        primary_contact_mobile=primary_contact_mobile,
        is_active=True,
        created_by_user_id=ctx.user_id,
    )
    db.add(company)
    db.flush()
    for loc_id in location_ids:
        db.add(VendorCompanyLocation(vendor_company_id=company.id, location_id=loc_id, is_active=True))
    AuditService(db).record(
        action="VENDOR_COMPANY_CREATED",
        entity_type="vendor_company",
        entity_id=str(company.id),
        actor_id=ctx.user_id,
        actor_email=ctx.email,
        after_value={"name": company.name},
    )
    db.commit()
    return _build_company_dict(db, company)


def get_vendor_company(db: Session, ctx: AuthContext, company_id: int) -> Dict[str, Any]:
    _require_read(ctx)
    company = db.query(VendorCompany).filter(VendorCompany.id == company_id).first()
    if not company:
        raise VendorCompanyError("not_found", "Vendor company not found.", 404)
    assignments = db.query(VendorCompanyLocation).filter(
        VendorCompanyLocation.vendor_company_id == company_id,
        VendorCompanyLocation.is_active.is_(True),
    ).all()
    if ctx.location_ids:
        if not any(a.location_id in ctx.location_ids for a in assignments):
            raise VendorCompanyError("forbidden", "Permission denied.", 403)
    detail = _build_company_dict(db, company)
    detail["duplicate_warnings"] = [
        {"id": d.id, "name": d.name} for d in find_duplicate_vendor_companies(db, company.name)
        if d.id != company.id
    ]
    profiles = (
        db.query(VendorVisitorProfile)
        .filter(VendorVisitorProfile.vendor_company_id == company_id, VendorVisitorProfile.is_active.is_(True))
        .all()
    )
    contractors: List[Dict[str, Any]] = []
    for p in profiles:
        visitor = db.query(Visitor).filter(Visitor.id == p.visitor_id).first()
        if visitor:
            contractors.append({
                "visitor_id": visitor.id,
                "full_name": visitor.full_name,
                "email": visitor.email,
                "phone": visitor.phone,
                "trade_or_role": p.trade_or_role,
            })
    detail["contractors"] = contractors
    company_docs: List[Dict[str, Any]] = []
    company_reqs = (
        db.query(ComplianceRequirement)
        .filter(
            ComplianceRequirement.is_active.is_(True),
            ComplianceRequirement.document_owner_type == "COMPANY",
            ComplianceRequirement.document_required.is_(True),
        )
        .all()
    )
    from app.application.compliance_service import _find_current_document
    for req in company_reqs:
        current = _find_current_document(db, req, company_id, None)
        history = list_documents_for_owner(db, req.id, vendor_company_id=company_id)
        current_id = current.id if current else None
        company_docs.append({
            "requirement_id": req.id,
            "requirement_name": req.name,
            "requirement_code": req.code,
            "current_document_id": current_id,
            "current_status": current.status if current else None,
            "valid_until": current.valid_until.isoformat() if current and current.valid_until else None,
            "documents": [{**d, "is_current": d["id"] == current_id} for d in history],
        })
    detail["compliance_documents"] = company_docs
    return detail


def update_vendor_company(
    db: Session,
    ctx: AuthContext,
    company_id: int,
    is_active: Optional[bool] = None,
    primary_contact_name: Optional[str] = None,
    primary_contact_email: Optional[str] = None,
    primary_contact_mobile: Optional[str] = None,
) -> Dict[str, Any]:
    _require_manage(ctx)
    company = db.query(VendorCompany).filter(VendorCompany.id == company_id).first()
    if not company:
        raise VendorCompanyError("not_found", "Vendor company not found.", 404)
    if is_active is not None:
        company.is_active = is_active
    if primary_contact_name is not None:
        company.primary_contact_name = primary_contact_name
    if primary_contact_email is not None:
        company.primary_contact_email = primary_contact_email
    if primary_contact_mobile is not None:
        company.primary_contact_mobile = primary_contact_mobile
    AuditService(db).record(
        action="VENDOR_COMPANY_UPDATED",
        entity_type="vendor_company",
        entity_id=str(company.id),
        actor_id=ctx.user_id,
        actor_email=ctx.email,
    )
    db.commit()
    return _build_company_dict(db, company)


def link_visitor_profile(
    db: Session,
    ctx: AuthContext,
    vendor_company_id: int,
    visitor_id: int,
    trade_or_role: Optional[str] = None,
    employee_reference: Optional[str] = None,
) -> Dict[str, Any]:
    _require_manage(ctx)
    company = db.query(VendorCompany).filter(VendorCompany.id == vendor_company_id).first()
    if not company or not company.is_active:
        raise VendorCompanyError("not_found", "Vendor company not found.", 404)
    existing = (
        db.query(VendorVisitorProfile)
        .filter(VendorVisitorProfile.visitor_id == visitor_id, VendorVisitorProfile.vendor_company_id == vendor_company_id)
        .first()
    )
    if existing:
        existing.is_active = True
        if trade_or_role:
            existing.trade_or_role = trade_or_role
        if employee_reference:
            existing.employee_reference = employee_reference
    else:
        db.add(
            VendorVisitorProfile(
                visitor_id=visitor_id,
                vendor_company_id=vendor_company_id,
                trade_or_role=trade_or_role,
                employee_reference=employee_reference,
                is_active=True,
            )
        )
    db.commit()
    return {"visitor_id": visitor_id, "vendor_company_id": vendor_company_id}
