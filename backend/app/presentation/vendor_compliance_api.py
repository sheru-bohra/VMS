from __future__ import annotations

from datetime import datetime
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.application.auth_service import AuthContext
from app.application.compliance_document_service import (
    ComplianceDocumentError,
    get_document_download,
    reject_document,
    upload_document,
    verify_document,
)
from app.application.compliance_requirement_service import (
    ComplianceRequirementError,
    create_requirement,
    deactivate_requirement,
    list_requirements_admin,
    update_requirement,
)
from app.application.compliance_service import compliance_summary_for_visit, evaluate_visit_compliance
from app.application.compliance_visit_detail_service import ComplianceVisitDetailError, get_visit_compliance_detail
from app.application.vendor_company_service import (
    VendorCompanyError,
    create_vendor_company,
    get_vendor_company,
    list_vendor_companies,
    link_visitor_profile,
    update_vendor_company,
)
from app.application.vendor_visit_service import (
    VendorVisitError,
    create_vendor_visit,
    list_compliance_reviews,
    list_contractor_visits,
)
from app.core.errors import APIError
from app.infrastructure.database import get_db
from app.presentation.dependencies import require_auth
from app.presentation.schemas import (
    ComplianceReviewItem,
    ComplianceReviewListResponse,
    ComplianceSummaryResponse,
    ComplianceVisitItem,
    ContractorVisitListResponse,
    CreateVendorCompanyRequest,
    CreateVendorVisitRequest,
    VendorCompanyItem,
    VendorCompanyListResponse,
    VendorCompanyUpdateRequest,
    ComplianceDocumentItem,
    ComplianceRequirementItem,
    ComplianceVisitDetailResponse,
    CreateComplianceRequirementRequest,
    UpdateComplianceRequirementRequest,
    RejectDocumentRequest,
)

router = APIRouter(tags=["vendor-compliance"])


def _vendor_err(exc: VendorCompanyError | VendorVisitError) -> None:
    raise APIError(exc.status_code, exc.code, exc.message)


def _req_err(exc: ComplianceRequirementError) -> None:
    raise APIError(exc.status_code, exc.code, exc.message)


def _doc_err(exc: ComplianceDocumentError) -> None:
    raise APIError(exc.status_code, exc.code, exc.message)


def _detail_err(exc: ComplianceVisitDetailError) -> None:
    raise APIError(exc.status_code, exc.code, exc.message)


@router.get("/compliance/requirements")
def list_requirements(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
):
    from app.domain.enums import Permission, role_has_permission
    from app.domain.models import ComplianceRequirement
    if not role_has_permission(user.role, Permission.COMPLIANCE_READ):
        raise APIError(403, "forbidden", "Permission denied.")
    rows = db.query(ComplianceRequirement).filter(ComplianceRequirement.is_active.is_(True)).order_by(ComplianceRequirement.name).all()
    return [
        {
            "id": r.id,
            "code": r.code,
            "name": r.name,
            "document_owner_type": r.document_owner_type,
            "is_mandatory": r.is_mandatory,
            "validity_required": r.validity_required,
        }
        for r in rows
    ]


@router.get("/compliance/requirements/admin", response_model=List[ComplianceRequirementItem])
def list_requirements_admin_endpoint(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
    include_inactive: Annotated[bool, Query()] = True,
) -> List[ComplianceRequirementItem]:
    try:
        items = list_requirements_admin(db, user, include_inactive=include_inactive)
    except ComplianceRequirementError as exc:
        _req_err(exc)
    return [ComplianceRequirementItem(**i) for i in items]


@router.post("/compliance/requirements", response_model=ComplianceRequirementItem)
def create_requirement_endpoint(
    body: CreateComplianceRequirementRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
) -> ComplianceRequirementItem:
    try:
        detail = create_requirement(
            db, user,
            name=body.name,
            description=body.description,
            visitor_type_id=body.visitor_type_id,
            scope_type=body.scope_type,
            location_id=body.location_id,
            document_owner_type=body.document_owner_type,
            document_required=body.document_required,
            validity_required=body.validity_required,
            safety_acknowledgement_required=body.safety_acknowledgement_required,
            is_mandatory=body.is_mandatory,
            expiry_warning_days=body.expiry_warning_days,
            code=body.code,
        )
    except ComplianceRequirementError as exc:
        _req_err(exc)
    return ComplianceRequirementItem(**detail)


@router.patch("/compliance/requirements/{requirement_id}", response_model=ComplianceRequirementItem)
def update_requirement_endpoint(
    requirement_id: int,
    body: UpdateComplianceRequirementRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
) -> ComplianceRequirementItem:
    try:
        detail = update_requirement(
            db, user, requirement_id,
            name=body.name,
            description=body.description,
            is_mandatory=body.is_mandatory,
            validity_required=body.validity_required,
            expiry_warning_days=body.expiry_warning_days,
            document_required=body.document_required,
        )
    except ComplianceRequirementError as exc:
        _req_err(exc)
    return ComplianceRequirementItem(**detail)


@router.post("/compliance/requirements/{requirement_id}/deactivate", response_model=ComplianceRequirementItem)
def deactivate_requirement_endpoint(
    requirement_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
) -> ComplianceRequirementItem:
    try:
        detail = deactivate_requirement(db, user, requirement_id)
    except ComplianceRequirementError as exc:
        _req_err(exc)
    return ComplianceRequirementItem(**detail)


@router.get("/vendor-companies", response_model=VendorCompanyListResponse)
def list_companies(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
    search: Annotated[Optional[str], Query(max_length=100)] = None,
    location_id: Annotated[Optional[int], Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> VendorCompanyListResponse:
    try:
        items, total = list_vendor_companies(db, user, search=search, location_id=location_id, limit=limit, offset=offset)
    except VendorCompanyError as exc:
        _vendor_err(exc)
    return VendorCompanyListResponse(items=[VendorCompanyItem(**i) for i in items], total=total, limit=limit, offset=offset)


@router.post("/vendor-companies", response_model=VendorCompanyItem)
def create_company(
    body: CreateVendorCompanyRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
) -> VendorCompanyItem:
    try:
        detail = create_vendor_company(
            db, user,
            name=body.name,
            location_ids=body.location_ids,
            code=body.code,
            primary_contact_name=body.primary_contact_name,
            primary_contact_email=body.primary_contact_email,
            primary_contact_mobile=body.primary_contact_mobile,
        )
    except VendorCompanyError as exc:
        _vendor_err(exc)
    return VendorCompanyItem(**detail)


@router.get("/vendor-companies/{company_id}", response_model=VendorCompanyItem)
def get_company(
    company_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
) -> VendorCompanyItem:
    try:
        detail = get_vendor_company(db, user, company_id)
    except VendorCompanyError as exc:
        _vendor_err(exc)
    return VendorCompanyItem(**detail)


@router.patch("/vendor-companies/{company_id}", response_model=VendorCompanyItem)
def patch_company(
    company_id: int,
    body: VendorCompanyUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
) -> VendorCompanyItem:
    try:
        detail = update_vendor_company(
            db, user, company_id,
            is_active=body.is_active,
            primary_contact_name=body.primary_contact_name,
            primary_contact_email=body.primary_contact_email,
            primary_contact_mobile=body.primary_contact_mobile,
        )
    except VendorCompanyError as exc:
        _vendor_err(exc)
    return VendorCompanyItem(**detail)


@router.post("/vendor-visits", response_model=ComplianceVisitItem)
def create_vendor_visit_endpoint(
    body: CreateVendorVisitRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
) -> ComplianceVisitItem:
    try:
        detail = create_vendor_visit(
            db, user,
            location_id=body.location_id,
            visitor_type_code=body.visitor_type,
            vendor_company_id=body.vendor_company_id,
            full_name=body.full_name,
            mobile=body.mobile,
            email=body.email,
            host_id=body.host_id,
            work_purpose=body.work_purpose,
            visit_date=body.visit_date,
            arrival_time=body.arrival_time,
            expected_duration_minutes=body.expected_duration_minutes,
            safety_acknowledged=body.safety_acknowledged,
            po_work_order_reference=body.po_work_order_reference,
            company=body.company,
            work_area=body.work_area,
            vendor_supervisor=body.vendor_supervisor,
            trade_or_role=body.trade_or_role,
        )
    except VendorVisitError as exc:
        _vendor_err(exc)
    return ComplianceVisitItem(**detail)


@router.get("/compliance/reviews", response_model=ComplianceReviewListResponse)
def compliance_reviews(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
    search: Annotated[Optional[str], Query(max_length=100)] = None,
    site: Annotated[Optional[int], Query()] = None,
    tab: Annotated[Optional[str], Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ComplianceReviewListResponse:
    try:
        items, total, attention, expiring = list_compliance_reviews(
            db, user, search=search, site=site, tab=tab, limit=limit, offset=offset,
        )
    except VendorVisitError as exc:
        _vendor_err(exc)
    return ComplianceReviewListResponse(
        items=[ComplianceReviewItem(**i) for i in items],
        total=total,
        attention_count=attention,
        expiring_count=expiring,
        limit=limit,
        offset=offset,
    )


@router.get("/compliance/contractor-visits", response_model=ContractorVisitListResponse)
def contractor_visits(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
    search: Annotated[Optional[str], Query(max_length=100)] = None,
    site: Annotated[Optional[int], Query()] = None,
    compliance_status: Annotated[Optional[str], Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ContractorVisitListResponse:
    try:
        items, total = list_contractor_visits(
            db, user, search=search, site=site, compliance_status=compliance_status, limit=limit, offset=offset,
        )
    except VendorVisitError as exc:
        _vendor_err(exc)
    return ContractorVisitListResponse(
        items=[ComplianceReviewItem(**i) for i in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/compliance/visits/{visit_id}/detail", response_model=ComplianceVisitDetailResponse)
def compliance_visit_detail(
    visit_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
) -> ComplianceVisitDetailResponse:
    try:
        detail = get_visit_compliance_detail(db, user, visit_id)
    except ComplianceVisitDetailError as exc:
        _detail_err(exc)
    return ComplianceVisitDetailResponse(**detail)


@router.get("/compliance/visits/{visit_id}", response_model=ComplianceSummaryResponse)
def compliance_for_visit(
    visit_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
) -> ComplianceSummaryResponse:
    evaluate_visit_compliance(db, visit_id, trigger="api")
    db.commit()
    summary = compliance_summary_for_visit(db, visit_id)
    return ComplianceSummaryResponse(**summary)


@router.post("/compliance/visits/{visit_id}/evaluate", response_model=ComplianceSummaryResponse)
def evaluate_compliance(
    visit_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
) -> ComplianceSummaryResponse:
    evaluate_visit_compliance(db, visit_id, trigger="manual")
    db.commit()
    return ComplianceSummaryResponse(**compliance_summary_for_visit(db, visit_id))


@router.post("/compliance-documents", response_model=ComplianceDocumentItem)
async def upload_compliance_document(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
    requirement_id: Annotated[int, Form()],
    file: UploadFile = File(...),
    vendor_company_id: Annotated[Optional[int], Form()] = None,
    visitor_id: Annotated[Optional[int], Form()] = None,
    visit_id: Annotated[Optional[int], Form()] = None,
    valid_from: Annotated[Optional[str], Form()] = None,
    valid_until: Annotated[Optional[str], Form()] = None,
    supersedes_id: Annotated[Optional[int], Form()] = None,
) -> ComplianceDocumentItem:
    content = await file.read()
    from io import BytesIO
    vf = datetime.fromisoformat(valid_from.replace("Z", "+00:00")) if valid_from else None
    vu = datetime.fromisoformat(valid_until.replace("Z", "+00:00")) if valid_until else None
    try:
        detail = upload_document(
            db, user,
            requirement_id=requirement_id,
            file_stream=BytesIO(content),
            file_name=file.filename or "document",
            mime_type=file.content_type,
            size_bytes=len(content),
            vendor_company_id=vendor_company_id,
            visitor_id=visitor_id,
            valid_from=vf,
            valid_until=vu,
            visit_id=visit_id,
            supersedes_id=supersedes_id,
        )
    except ComplianceDocumentError as exc:
        _doc_err(exc)
    return ComplianceDocumentItem(**detail)


@router.post("/compliance-documents/{document_id}/verify", response_model=ComplianceDocumentItem)
def verify_doc(
    document_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
    visit_id: Annotated[Optional[int], Query()] = None,
) -> ComplianceDocumentItem:
    try:
        detail = verify_document(db, user, document_id, visit_id=visit_id)
    except ComplianceDocumentError as exc:
        _doc_err(exc)
    return ComplianceDocumentItem(**detail)


@router.post("/compliance-documents/{document_id}/reject", response_model=ComplianceDocumentItem)
def reject_doc(
    document_id: int,
    body: RejectDocumentRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
    visit_id: Annotated[Optional[int], Query()] = None,
) -> ComplianceDocumentItem:
    try:
        detail = reject_document(db, user, document_id, body.comment, visit_id=visit_id)
    except ComplianceDocumentError as exc:
        _doc_err(exc)
    return ComplianceDocumentItem(**detail)


@router.get("/compliance-documents/{document_id}/download")
def download_doc(
    document_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
):
    try:
        name, mime, data = get_document_download(db, user, document_id)
    except ComplianceDocumentError as exc:
        _doc_err(exc)
    safe_name = name.replace('"', "").replace("\n", "").replace("\r", "")
    return Response(
        content=data,
        media_type=mime,
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
