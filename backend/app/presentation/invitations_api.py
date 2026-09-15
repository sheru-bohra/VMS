from __future__ import annotations

from io import BytesIO
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.orm import Session

from app.application.auth_service import AuthContext
from app.application.invitation_service import (
    InvitationError,
    cancel_invitation,
    create_advance_visit,
    get_invitation_detail,
    get_invitation_qr_meta,
    list_invitations,
)
from app.application.registration_attachment_service import (
    RegistrationAttachmentError,
    save_registration_attachment,
)
from app.application.visitor_media_service import (
    VisitorMediaError,
    delete_staged_photo,
    stage_visitor_photo,
)
from app.core.errors import APIError
from app.infrastructure.database import get_db
from app.presentation.dependencies import require_auth
from app.presentation.schemas import (
    CancelInvitationRequest,
    CreateInvitationRequest,
    InvitationItem,
    InvitationListResponse,
    RegistrationAttachmentResponse,
    VisitorPhotoStageResponse,
)

router = APIRouter(tags=["invitations"])


def _handle(exc: InvitationError) -> None:
    raise APIError(exc.status_code, exc.code, exc.message)


def _handle_attachment(exc: RegistrationAttachmentError) -> None:
    raise APIError(exc.status_code, exc.code, exc.message)


@router.get("/invitations", response_model=InvitationListResponse)
def list_invitation_queue(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
    tab: Annotated[Optional[str], Query()] = None,
    search: Annotated[Optional[str], Query(max_length=100)] = None,
    site: Annotated[Optional[int], Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> InvitationListResponse:
    try:
        items, total = list_invitations(db, user, tab=tab, search=search, site=site, limit=limit, offset=offset)
    except InvitationError as exc:
        _handle(exc)
    return InvitationListResponse(
        items=[InvitationItem(**item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


def _handle_media(exc: VisitorMediaError) -> None:
    raise APIError(exc.status_code, exc.code, exc.message)


@router.post("/invitations/visitor-photo", response_model=VisitorPhotoStageResponse)
async def stage_visitor_photo_upload(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
    file: UploadFile = File(...),
    full_name: Annotated[Optional[str], Form()] = None,
    source: Annotated[str, Form()] = "UPLOAD",
    location_id: Annotated[Optional[int], Form()] = None,
) -> VisitorPhotoStageResponse:
    content = await file.read()
    try:
        detail = stage_visitor_photo(
            db,
            user,
            BytesIO(content),
            file.filename or "photo.jpg",
            file.content_type,
            len(content),
            full_name=full_name,
            source=source,
            location_id=location_id,
        )
    except VisitorMediaError as exc:
        _handle_media(exc)
    return VisitorPhotoStageResponse(**detail)


@router.delete("/invitations/visitor-photo/{media_id}")
def delete_staged_visitor_photo(
    media_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
) -> dict:
    try:
        delete_staged_photo(db, user, media_id)
    except VisitorMediaError as exc:
        _handle_media(exc)
    return {"ok": True}


@router.post("/invitations/registration-attachments", response_model=RegistrationAttachmentResponse)
async def upload_registration_attachment(
    user: Annotated[AuthContext, Depends(require_auth)],
    kind: Annotated[str, Form()],
    file: UploadFile = File(...),
) -> RegistrationAttachmentResponse:
    content = await file.read()
    try:
        detail = save_registration_attachment(
            user,
            kind,
            BytesIO(content),
            file.filename or "upload",
            file.content_type,
            len(content),
        )
    except RegistrationAttachmentError as exc:
        _handle_attachment(exc)
    return RegistrationAttachmentResponse(**detail)


@router.post("/invitations", response_model=InvitationItem)
def create_invitation(
    body: CreateInvitationRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
) -> InvitationItem:
    try:
        detail = create_advance_visit(
            db, user,
            location_id=body.location_id,
            visitor_type_code=body.visitor_type,
            full_name=body.full_name,
            mobile=body.mobile,
            email=body.email,
            company=body.company,
            host_id=body.host_id,
            visit_date=body.visit_date,
            arrival_time=body.arrival_time,
            expected_duration_minutes=body.expected_duration_minutes,
            purpose=body.purpose,
            notes=body.notes,
            policy_accepted=body.policy_accepted,
            departure_time=body.departure_time,
            designation=body.designation,
            address=body.address,
            vendor_company_id=body.vendor_company_id,
            work_purpose=body.work_purpose,
            po_work_order_reference=body.po_work_order_reference,
            safety_acknowledged=body.safety_acknowledged,
            govt_id_type=body.govt_id_type,
            govt_id_number=body.govt_id_number,
            photo_storage_key=body.photo_storage_key,
            photo_media_id=body.photo_media_id,
            signature_storage_key=body.signature_storage_key,
            id_image_storage_key=body.id_image_storage_key,
            nda_signed=body.nda_signed,
            ppe_required=body.ppe_required,
            safety_induction_completed=body.safety_induction_completed,
            assets=body.assets,
            assets_other=body.assets_other,
            vehicle_number=body.vehicle_number,
            vehicle_type=body.vehicle_type,
        )
    except InvitationError as exc:
        _handle(exc)
    return InvitationItem(**detail)


@router.get("/invitations/{visit_id}", response_model=InvitationItem)
def get_invitation(
    visit_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
) -> InvitationItem:
    try:
        detail = get_invitation_detail(db, user, visit_id)
    except InvitationError as exc:
        _handle(exc)
    return InvitationItem(**detail)


@router.get("/invitations/{visit_id}/qr", response_model=InvitationItem)
def get_invitation_qr(
    visit_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
) -> InvitationItem:
    try:
        detail = get_invitation_qr_meta(db, user, visit_id)
    except InvitationError as exc:
        _handle(exc)
    return InvitationItem(**detail)


@router.post("/invitations/{visit_id}/cancel", response_model=InvitationItem)
def cancel_invitation_visit(
    visit_id: int,
    body: CancelInvitationRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
) -> InvitationItem:
    try:
        detail = cancel_invitation(db, user, visit_id, body.reason)
    except InvitationError as exc:
        _handle(exc)
    return InvitationItem(**detail)
