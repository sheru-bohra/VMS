"""Vendor/contractor visit creation and compliance review queue."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session, joinedload

from app.application.auth_service import AuthContext
from app.application.compliance_service import evaluate_visit_compliance, compliance_summary_for_visit
from app.application.invitation_service import InvitationError, _build_invitation_dict, _load_visit, _require_create, _require_site
from app.application.registration_service import (
    find_or_create_visitor,
    generate_registration_reference,
    normalize_email,
    normalize_name,
    normalize_phone,
    RegistrationError,
    validate_host_for_site,
    validate_visitor_type,
)
from app.application.audit_service import AuditService
from app.application.site_scope_service import apply_location_scope, can_access_location
from app.core.config import settings
from app.domain.enums import ComplianceStatus, Permission, VisitSource, VisitStatus, role_has_permission
from app.domain.models import (
    ComplianceEvaluation,
    Location,
    VendorCompany,
    VendorCompanyLocation,
    VendorVisitDetails,
    VendorVisitorProfile,
    Visit,
    Visitor,
)


class VendorVisitError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _parse_schedule(visit_date: str, arrival_time: str, timezone_name: Optional[str]) -> datetime:
    from app.application.invitation_service import parse_scheduled_start
    return parse_scheduled_start(visit_date, arrival_time, timezone_name)


def create_vendor_visit(
    db: Session,
    ctx: AuthContext,
    location_id: int,
    visitor_type_code: str,
    vendor_company_id: int,
    full_name: str,
    mobile: str,
    email: str,
    host_id: int,
    work_purpose: str,
    visit_date: str,
    arrival_time: str,
    expected_duration_minutes: int,
    safety_acknowledged: bool,
    po_work_order_reference: Optional[str] = None,
    company: Optional[str] = None,
    work_area: Optional[str] = None,
    vendor_supervisor: Optional[str] = None,
    trade_or_role: Optional[str] = None,
) -> Dict[str, Any]:
    _require_create(ctx)
    _require_site(ctx, location_id)

    company_row = db.query(VendorCompany).filter(VendorCompany.id == vendor_company_id).first()
    if not company_row or not company_row.is_active:
        raise VendorVisitError("invalid_vendor", "Vendor company not found or inactive.")

    assignment = (
        db.query(VendorCompanyLocation)
        .filter(
            VendorCompanyLocation.vendor_company_id == vendor_company_id,
            VendorCompanyLocation.location_id == location_id,
            VendorCompanyLocation.is_active.is_(True),
        )
        .first()
    )
    if not assignment:
        raise VendorVisitError("vendor_location", "Vendor company is not assigned to this location.")

    location = db.query(Location).filter(Location.id == location_id).first()
    scheduled_start = _parse_schedule(visit_date, arrival_time, location.timezone if location else None)
    now = datetime.now(timezone.utc)
    if scheduled_start < now - timedelta(minutes=5):
        raise VendorVisitError("invalid_schedule", "Visit date cannot be in the past.")

    try:
        visitor_type = validate_visitor_type(db, visitor_type_code)
        host = validate_host_for_site(db, host_id, location_id)
    except RegistrationError as exc:
        raise VendorVisitError(exc.code, exc.message)

    if not visitor_type.requires_vendor_compliance:
        raise VendorVisitError("invalid_type", "Selected visitor type does not require vendor compliance flow.")

    if visitor_type.po_reference_required and not (po_work_order_reference and po_work_order_reference.strip()):
        raise VendorVisitError("po_required", "PO / Work Order reference is required.")

    if not safety_acknowledged:
        raise VendorVisitError("safety_required", "Safety acknowledgement is required.")

    full_name = normalize_name(full_name)
    audit = AuditService(db)
    visitor, _ = find_or_create_visitor(
        db,
        full_name,
        mobile,
        email,
        company or company_row.name,
        visitor_type.id,
        audit,
    )

    profile = (
        db.query(VendorVisitorProfile)
        .filter(VendorVisitorProfile.visitor_id == visitor.id, VendorVisitorProfile.vendor_company_id == vendor_company_id)
        .first()
    )
    if not profile:
        db.add(
            VendorVisitorProfile(
                visitor_id=visitor.id,
                vendor_company_id=vendor_company_id,
                trade_or_role=trade_or_role,
                is_active=True,
            )
        )
    elif trade_or_role:
        profile.trade_or_role = trade_or_role

    reference = generate_registration_reference(db)
    scheduled_end = scheduled_start + timedelta(minutes=expected_duration_minutes)

    visit = Visit(
        visitor_id=visitor.id,
        location_id=location_id,
        status=VisitStatus.PENDING_APPROVAL.value,
        registration_reference=reference,
        host_id=host.id,
        host_name=host.name,
        purpose=work_purpose.strip(),
        expected_duration_minutes=expected_duration_minutes,
        expected_arrival=scheduled_start,
        scheduled_start=scheduled_start,
        scheduled_end=scheduled_end,
        policy_accepted=True,
        policy_accepted_at=now,
        source=VisitSource.ADVANCE_REGISTRATION.value,
        created_by_user_id=ctx.user_id,
        invitation_active=False,
    )
    db.add(visit)
    db.flush()

    db.add(
        VendorVisitDetails(
            visit_id=visit.id,
            vendor_company_id=vendor_company_id,
            work_purpose=work_purpose.strip(),
            po_work_order_reference=po_work_order_reference,
            work_area=work_area,
            vendor_supervisor=vendor_supervisor,
            company_contact_host_id=host.id,
            safety_acknowledged=True,
            safety_acknowledged_at=now,
            safety_policy_version=settings.safety_policy_version,
        )
    )

    audit.record(
        action="SAFETY_ACKNOWLEDGED",
        entity_type="visit",
        entity_id=str(visit.id),
        actor_id=ctx.user_id,
        actor_email=ctx.email,
        location_id=location_id,
        after_value={"policy_version": settings.safety_policy_version},
    )
    audit.record(
        action="VENDOR_VISIT_CREATED",
        entity_type="visit",
        entity_id=str(visit.id),
        actor_id=ctx.user_id,
        actor_email=ctx.email,
        location_id=location_id,
        after_value={"vendor_company_id": vendor_company_id, "reference": reference},
    )

    from app.application.host_approval_service import maybe_create_for_pending_visit
    maybe_create_for_pending_visit(db, visit.id)

    from app.application.security_screening_service import screen_visit
    screen_visit(db, visit.id, trigger="vendor_visit")
    evaluate_visit_compliance(db, visit.id, trigger="vendor_visit")

    db.commit()

    from app.application.notification_dispatch_service import dispatch_pending_notifications
    dispatch_pending_notifications(db)

    result = _build_invitation_dict(db, _load_visit(db, visit.id) or visit)
    result["compliance"] = compliance_summary_for_visit(db, visit.id)
    result["vendor_company_id"] = vendor_company_id
    return result


def list_compliance_reviews(
    db: Session,
    ctx: AuthContext,
    search: Optional[str] = None,
    site: Optional[int] = None,
    tab: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[List[Dict[str, Any]], int, int, int]:
    if not role_has_permission(ctx.role, Permission.COMPLIANCE_READ):
        raise VendorVisitError("forbidden", "Permission denied.", 403)

    base_query = (
        db.query(Visit)
        .options(joinedload(Visit.visitor), joinedload(Visit.vendor_visit_details), joinedload(Visit.location))
    )
    base_query = apply_location_scope(base_query, ctx, db, site)

    attention_count = base_query.filter(
        Visit.compliance_status.in_([
            ComplianceStatus.REVIEW_REQUIRED.value,
            ComplianceStatus.NON_COMPLIANT.value,
        ])
    ).count()

    expiring_count = base_query.filter(
        Visit.compliance_status == ComplianceStatus.EXPIRING.value
    ).count()

    query = base_query
    if tab == "expiring":
        query = query.filter(Visit.compliance_status == ComplianceStatus.EXPIRING.value)
    elif tab == "cleared":
        query = query.filter(Visit.compliance_status == ComplianceStatus.COMPLIANT.value)
    else:
        query = query.filter(
            Visit.compliance_status.in_([
                ComplianceStatus.REVIEW_REQUIRED.value,
                ComplianceStatus.NON_COMPLIANT.value,
                ComplianceStatus.EXPIRING.value,
            ])
        )

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.join(Visitor, Visit.visitor_id == Visitor.id).filter(
            Visitor.full_name.ilike(term) | Visit.registration_reference.ilike(term)
        )

    total = query.count()
    visits = query.order_by(Visit.updated_at.desc()).offset(offset).limit(limit).all()
    items: List[Dict[str, Any]] = []
    for v in visits:
        vendor_name = None
        if v.vendor_visit_details:
            vc = db.query(VendorCompany).filter(VendorCompany.id == v.vendor_visit_details.vendor_company_id).first()
            vendor_name = vc.name if vc else None
        latest = (
            db.query(ComplianceEvaluation)
            .filter(ComplianceEvaluation.visit_id == v.id)
            .order_by(ComplianceEvaluation.evaluated_at.desc())
            .first()
        )
        items.append({
            "visit_id": v.id,
            "registration_reference": v.registration_reference,
            "visitor_name": v.visitor.full_name if v.visitor else "",
            "vendor_company_name": vendor_name,
            "site_name": v.location.name if v.location else "",
            "site_id": v.location_id,
            "compliance_status": v.compliance_status,
            "issue": latest.reason_summary if latest else v.compliance_status,
            "status": v.status,
        })
    return items, total, attention_count, expiring_count


def list_contractor_visits(
    db: Session,
    ctx: AuthContext,
    search: Optional[str] = None,
    site: Optional[int] = None,
    compliance_status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[List[Dict[str, Any]], int]:
    if not role_has_permission(ctx.role, Permission.COMPLIANCE_READ):
        raise VendorVisitError("forbidden", "Permission denied.", 403)
    query = (
        db.query(Visit)
        .options(joinedload(Visit.visitor), joinedload(Visit.vendor_visit_details), joinedload(Visit.location))
        .join(VendorVisitDetails)
    )
    query = apply_location_scope(query, ctx, db, site)
    if compliance_status:
        query = query.filter(Visit.compliance_status == compliance_status.upper())
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.join(Visitor, Visit.visitor_id == Visitor.id).filter(
            Visitor.full_name.ilike(term) | Visit.registration_reference.ilike(term)
        )
    total = query.count()
    visits = query.order_by(Visit.scheduled_start.desc().nullslast()).offset(offset).limit(limit).all()
    items = []
    for v in visits:
        vendor_name = None
        if v.vendor_visit_details:
            vc = db.query(VendorCompany).filter(VendorCompany.id == v.vendor_visit_details.vendor_company_id).first()
            vendor_name = vc.name if vc else None
        items.append({
            "visit_id": v.id,
            "registration_reference": v.registration_reference,
            "visitor_name": v.visitor.full_name if v.visitor else "",
            "vendor_company_name": vendor_name,
            "site_name": v.location.name if v.location else "",
            "compliance_status": v.compliance_status,
            "status": v.status,
            "scheduled_start": v.scheduled_start.isoformat() if v.scheduled_start else None,
        })
    return items, total
