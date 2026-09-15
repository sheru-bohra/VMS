"""Compliance visit detail for operational UI."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session, joinedload

from app.application.auth_service import AuthContext
from app.application.compliance_service import (
    _company_requirement_applicable,
    _document_usability,
    _find_current_document,
    _registration_satisfies_requirement,
    _resolve_po_reference,
    _resolve_safety_acknowledged,
    _resolve_vendor_company_id,
    compliance_summary_for_visit,
    evaluate_visit_compliance,
    get_evaluation_datetime,
    load_applicable_requirements,
    visitor_type_requires_compliance,
)
from app.application.compliance_document_service import list_documents_for_owner
from app.application.site_scope_service import can_access_location
from app.domain.enums import ComplianceDocumentOwnerType, Permission, role_has_permission
from app.domain.models import AdminUser, Location, VendorCompany, Visit, VisitorType


class ComplianceVisitDetailError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _require_read(ctx: AuthContext) -> None:
    if not role_has_permission(ctx.role, Permission.COMPLIANCE_READ):
        raise ComplianceVisitDetailError("forbidden", "Permission denied.", 403)


def get_visit_compliance_detail(db: Session, ctx: AuthContext, visit_id: int) -> Dict[str, Any]:
    _require_read(ctx)
    visit = (
        db.query(Visit)
        .options(
            joinedload(Visit.visitor),
            joinedload(Visit.vendor_visit_details),
            joinedload(Visit.location),
        )
        .filter(Visit.id == visit_id)
        .first()
    )
    if not visit:
        raise ComplianceVisitDetailError("not_found", "Visit not found.", 404)
    if not can_access_location(ctx, visit.location_id):
        raise ComplianceVisitDetailError("forbidden", "Permission denied.", 403)

    evaluate_visit_compliance(db, visit_id, trigger="detail_view")
    db.commit()

    visitor = visit.visitor
    vendor_company_id = _resolve_vendor_company_id(visit)
    vendor_name = None
    if vendor_company_id:
        vc = db.query(VendorCompany).filter(VendorCompany.id == vendor_company_id).first()
        vendor_name = vc.name if vc else None

    visitor_type_name = None
    if visitor and visitor.visitor_type_id:
        vt = db.query(VisitorType).filter(VisitorType.id == visitor.visitor_type_id).first()
        visitor_type_name = vt.name if vt else None

    evaluation_dt = get_evaluation_datetime(visit)
    requirements_payload: List[Dict[str, Any]] = []

    if visitor and visitor_type_requires_compliance(db, visitor.visitor_type_id):
        applicable = load_applicable_requirements(db, visitor.visitor_type_id, visit.location_id)
        for req in applicable:
            if not req.document_required:
                continue
            if not _company_requirement_applicable(req, vendor_company_id):
                continue
            if _registration_satisfies_requirement(req, visit):
                requirements_payload.append({
                    "requirement_id": req.id,
                    "requirement_code": req.code,
                    "requirement_name": req.name,
                    "document_owner_type": req.document_owner_type,
                    "is_mandatory": req.is_mandatory,
                    "validity_required": req.validity_required,
                    "usability": "valid",
                    "current_document_id": None,
                    "documents": [],
                })
                continue
            current_doc = _find_current_document(db, req, vendor_company_id, visitor.id)
            usability, _ = _document_usability(current_doc, req, evaluation_dt)
            owner_id = vendor_company_id if req.document_owner_type == ComplianceDocumentOwnerType.COMPANY.value else visitor.id
            history = list_documents_for_owner(
                db,
                requirement_id=req.id,
                vendor_company_id=vendor_company_id if req.document_owner_type == ComplianceDocumentOwnerType.COMPANY.value else None,
                visitor_id=visitor.id if req.document_owner_type == ComplianceDocumentOwnerType.VISITOR.value else None,
            )
            current_id = current_doc.id if current_doc else None
            requirements_payload.append({
                "requirement_id": req.id,
                "requirement_code": req.code,
                "requirement_name": req.name,
                "document_owner_type": req.document_owner_type,
                "is_mandatory": req.is_mandatory,
                "validity_required": req.validity_required,
                "usability": usability,
                "current_document_id": current_id,
                "documents": [
                    {**d, "is_current": d["id"] == current_id}
                    for d in history
                ],
            })

    summary = compliance_summary_for_visit(db, visit_id)
    return {
        "visit_id": visit.id,
        "registration_reference": visit.registration_reference,
        "status": visit.status,
        "visitor_id": visitor.id if visitor else None,
        "visitor_name": visitor.full_name if visitor else "",
        "visitor_mobile": visitor.phone if visitor else None,
        "visitor_email": visitor.email if visitor else None,
        "visitor_type": visitor_type_name,
        "vendor_company_id": vendor_company_id,
        "vendor_company_name": vendor_name,
        "site_id": visit.location_id,
        "site_name": visit.location.name if visit.location else None,
        "host_name": visit.host_name,
        "work_purpose": visit.vendor_visit_details.work_purpose if visit.vendor_visit_details else visit.purpose,
        "po_work_order_reference": _resolve_po_reference(visit),
        "safety_acknowledged": _resolve_safety_acknowledged(visit),
        "safety_acknowledged_at": (
            visit.vendor_visit_details.safety_acknowledged_at.isoformat()
            if visit.vendor_visit_details and visit.vendor_visit_details.safety_acknowledged_at
            else None
        ),
        "scheduled_start": visit.scheduled_start.isoformat() if visit.scheduled_start else None,
        "evaluation_date": evaluation_dt.isoformat(),
        "compliance": summary,
        "requirements": requirements_payload,
    }
