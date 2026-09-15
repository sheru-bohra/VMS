"""Advance visit invitations and visitor QR lifecycle."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.application.audit_service import AuditService
from app.application.auth_service import AuthContext
from app.application.registration_service import (
    find_or_create_visitor,
    generate_registration_reference,
    normalize_email,
    normalize_name,
    normalize_phone,
    RegistrationError,
    validate_host_for_site,
    validate_visitor_type,
    CURRENT_POLICY_VERSION,
)
from app.application.site_scope_service import apply_location_scope, can_access_location
from app.application.timezone_service import get_location_day_bounds, resolve_timezone
from app.application.token_service import generate_invitation_token
from app.core.config import settings
from app.domain.enums import Permission, VisitSource, VisitStatus, role_has_permission, NotificationType
from app.domain.models import AdminUser, Location, Visit, Visitor, VisitorType, VendorCompany, VendorCompanyLocation, VendorVisitDetails, VendorVisitorProfile, VisitorMedia
from app.domain.visit_state import validate_transition

ALLOWED_DURATIONS = frozenset({30, 60, 120, 240, 480})
MAX_NOTES_LENGTH = 500
MAX_CANCEL_REASON_LENGTH = 500


def _queue_visitor_invitation_notification(db: Session, visit: Visit, valid_until: datetime) -> None:
    visitor = visit.visitor
    if not visitor or not visitor.email:
        return
    if not visit.invitation_token:
        return
    location = db.query(Location).filter(Location.id == visit.location_id).first()
    invitation_url = f"{settings.public_app_origin}/visit/invitation/{visit.invitation_token}"
    scheduled_display = None
    if visit.scheduled_start:
        scheduled_display = visit.scheduled_start.strftime("%d %b %Y · %I:%M %p")
    payload = {
        "visitor_name": visitor.full_name,
        "site_name": location.name if location else "",
        "host_name": visit.host_name,
        "purpose": visit.purpose,
        "registration_reference": visit.registration_reference,
        "scheduled_display": scheduled_display,
        "invitation_url": invitation_url,
        "location_id": visit.location_id,
    }
    try:
        from app.application.invitation_qr_service import invitation_qr_png_base64
        payload["qr_png_base64"] = invitation_qr_png_base64(invitation_url)
    except Exception:
        pass
    from app.application.notification_service import queue_visitor_invitation_email
    version = valid_until.isoformat()
    queue_visitor_invitation_email(
        db,
        visit_id=visit.id,
        visitor_email=visitor.email,
        location_id=visit.location_id,
        payload=payload,
        invitation_version=version,
    )


class InvitationError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def validate_indian_mobile(mobile: str) -> str:
    digits = re.sub(r"\D", "", mobile.strip())
    if not re.fullmatch(r"\d{10}", digits):
        raise InvitationError("invalid_mobile", "Enter a valid 10-digit mobile number.")
    return digits


def _require_read(ctx: AuthContext) -> None:
    if not role_has_permission(ctx.role, Permission.INVITATION_READ):
        raise InvitationError("forbidden", "Permission denied.", 403)


def _require_create(ctx: AuthContext) -> None:
    if not role_has_permission(ctx.role, Permission.INVITATION_CREATE):
        raise InvitationError("forbidden", "Permission denied.", 403)


def _require_cancel(ctx: AuthContext) -> None:
    if not role_has_permission(ctx.role, Permission.INVITATION_CANCEL):
        raise InvitationError("forbidden", "Permission denied.", 403)


def _require_site(ctx: AuthContext, location_id: int) -> None:
    if not can_access_location(ctx, location_id):
        raise InvitationError("LOCATION_ACCESS_DENIED", "You do not have access to this site.", 403)


def _load_visit(db: Session, visit_id: int) -> Optional[Visit]:
    return (
        db.query(Visit)
        .options(
            joinedload(Visit.visitor).joinedload(Visitor.visitor_type),
            joinedload(Visit.location),
            joinedload(Visit.approvals),
        )
        .filter(Visit.id == visit_id)
        .first()
    )


def _load_by_token(db: Session, token: str) -> Optional[Visit]:
    return (
        db.query(Visit)
        .options(
            joinedload(Visit.visitor).joinedload(Visitor.visitor_type),
            joinedload(Visit.location),
            joinedload(Visit.approvals),
        )
        .filter(Visit.invitation_token == token)
        .first()
    )


def _invitation_status(visit: Visit, now: Optional[datetime] = None) -> str:
    if visit.status in (VisitStatus.REJECTED.value, VisitStatus.CANCELLED.value):
        return "INVALID"
    if visit.status == VisitStatus.CHECKED_OUT.value:
        return "COMPLETED"
    if not visit.invitation_active or not visit.invitation_token:
        if visit.status == VisitStatus.PENDING_APPROVAL.value:
            return "PENDING_APPROVAL"
        return "NOT_ACTIVE"
    now = now or datetime.now(timezone.utc)
    vf = visit.invitation_valid_from
    vu = visit.invitation_valid_until
    if vf and vf.tzinfo is None:
        vf = vf.replace(tzinfo=timezone.utc)
    if vu and vu.tzinfo is None:
        vu = vu.replace(tzinfo=timezone.utc)
    if vf and now < vf:
        return "NOT_YET_VALID"
    if vu and now > vu:
        return "EXPIRED"
    return "ACTIVE"


def _build_invitation_dict(db: Session, visit: Visit) -> Dict[str, Any]:
    visitor = visit.visitor
    location = visit.location
    visitor_type_name = visitor.visitor_type.name if visitor and visitor.visitor_type else None
    created_by_email = None
    if visit.created_by_user_id:
        creator = db.query(AdminUser).filter(AdminUser.id == visit.created_by_user_id).first()
        if creator:
            created_by_email = creator.email

    inv_status = _invitation_status(visit)
    has_qr = visit.invitation_active and visit.invitation_token and inv_status in ("ACTIVE", "NOT_YET_VALID")

    return {
        "id": visit.id,
        "registration_reference": visit.registration_reference,
        "status": visit.status,
        "source": visit.source,
        "visitor_name": visitor.full_name if visitor else "",
        "visitor_mobile": visitor.phone if visitor else None,
        "visitor_email": visitor.email if visitor else None,
        "company": visitor.company if visitor else None,
        "visitor_type": visitor_type_name,
        "host_name": visit.host_name,
        "site_name": location.name if location else "",
        "site_id": visit.location_id,
        "site_city": location.city if location else None,
        "purpose": visit.purpose,
        "notes": visit.notes,
        "expected_duration_minutes": visit.expected_duration_minutes,
        "scheduled_start": visit.scheduled_start.isoformat() if visit.scheduled_start else None,
        "scheduled_end": visit.scheduled_end.isoformat() if visit.scheduled_end else None,
        "submitted_at": visit.created_at.isoformat() if visit.created_at else None,
        "invitation_status": inv_status,
        "invitation_valid_from": visit.invitation_valid_from.isoformat() if visit.invitation_valid_from else None,
        "invitation_valid_until": visit.invitation_valid_until.isoformat() if visit.invitation_valid_until else None,
        "has_active_invitation": has_qr,
        "created_by_email": created_by_email,
        "cancelled_at": visit.cancelled_at.isoformat() if visit.cancelled_at else None,
        "cancellation_reason": visit.cancellation_reason,
        "approval_history": [
            {
                "id": a.id,
                "decision": a.decision,
                "actor_type": a.actor_type,
                "actor_email": a.actor_email,
                "actor_role": a.actor_role,
                "actor_name": a.actor_name,
                "comment": a.comment,
                "reason_code": a.reason_code,
                "previous_status": a.previous_status,
                "new_status": a.new_status,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in sorted(visit.approvals, key=lambda x: x.created_at or datetime.min.replace(tzinfo=timezone.utc))
        ],
    }


def parse_scheduled_start(visit_date: str, arrival_time: str, tz_name: Optional[str]) -> datetime:
    try:
        date_part = datetime.strptime(visit_date.strip(), "%Y-%m-%d").date()
        time_part = datetime.strptime(arrival_time.strip(), "%H:%M").time()
    except ValueError:
        raise InvitationError("invalid_schedule", "Invalid visit date or arrival time.")

    tz = resolve_timezone(tz_name)
    local = datetime(
        date_part.year, date_part.month, date_part.day,
        time_part.hour, time_part.minute, tzinfo=tz,
    )
    return local.astimezone(timezone.utc)


def _mask_identifier(value: str) -> str:
    v = value.strip()
    if len(v) <= 4:
        return "••••"
    return "••••" + v[-4:]


def _build_registration_metadata(
    govt_id_type: Optional[str],
    govt_id_number: Optional[str],
    photo_storage_key: Optional[str],
    signature_storage_key: Optional[str],
    id_image_storage_key: Optional[str],
    nda_signed: bool,
    ppe_required: bool,
    safety_induction_completed: bool,
    assets: Optional[List[str]],
    assets_other: Optional[str],
    vehicle_number: Optional[str],
    vehicle_type: Optional[str],
    departure_time: Optional[str],
    vendor_company_id: Optional[int],
    po_work_order_reference: Optional[str] = None,
) -> Dict[str, Any]:
    meta: Dict[str, Any] = {
        "nda_signed": nda_signed,
        "ppe_required": ppe_required,
        "safety_induction_completed": safety_induction_completed,
        "ocr_status": "unavailable",
    }
    if govt_id_type:
        meta["govt_id_type"] = govt_id_type.strip()[:50]
    if govt_id_number and govt_id_number.strip():
        raw = govt_id_number.strip()
        meta["govt_id_masked"] = _mask_identifier(raw)
        import base64
        from app.application.document_encryption import DocumentEncryptionError, encrypt_bytes

        try:
            blob, enc_version = encrypt_bytes(raw.encode("utf-8"))
            meta["govt_id_encrypted"] = base64.b64encode(blob).decode("ascii")
            meta["govt_id_enc_version"] = enc_version
        except DocumentEncryptionError:
            if settings.is_production:
                raise InvitationError(
                    "encryption_unavailable",
                    "Government ID encryption is not configured.",
                    503,
                )
    if photo_storage_key:
        meta["photo_storage_key"] = photo_storage_key
    if signature_storage_key:
        meta["signature_storage_key"] = signature_storage_key
    if id_image_storage_key:
        meta["id_image_storage_key"] = id_image_storage_key
    if assets:
        meta["assets"] = assets[:20]
    if assets_other:
        meta["assets_other"] = assets_other.strip()[:200]
    if vehicle_number:
        meta["vehicle_number"] = vehicle_number.strip()[:30]
    if vehicle_type:
        meta["vehicle_type"] = vehicle_type.strip()[:30]
    if departure_time:
        meta["departure_time"] = departure_time.strip()
    if vendor_company_id:
        meta["vendor_company_id"] = vendor_company_id
    if po_work_order_reference and po_work_order_reference.strip():
        meta["po_work_order_reference"] = po_work_order_reference.strip()
    return meta


def create_advance_visit(
    db: Session,
    ctx: AuthContext,
    location_id: int,
    visitor_type_code: str,
    full_name: str,
    mobile: str,
    email: Optional[str],
    company: Optional[str],
    host_id: Optional[int],
    visit_date: str,
    arrival_time: str,
    expected_duration_minutes: int,
    purpose: str,
    notes: Optional[str] = None,
    policy_accepted: bool = True,
    departure_time: Optional[str] = None,
    designation: Optional[str] = None,
    address: Optional[str] = None,
    vendor_company_id: Optional[int] = None,
    work_purpose: Optional[str] = None,
    po_work_order_reference: Optional[str] = None,
    safety_acknowledged: bool = False,
    govt_id_type: Optional[str] = None,
    govt_id_number: Optional[str] = None,
    photo_storage_key: Optional[str] = None,
    photo_media_id: Optional[int] = None,
    signature_storage_key: Optional[str] = None,
    id_image_storage_key: Optional[str] = None,
    nda_signed: bool = False,
    ppe_required: bool = False,
    safety_induction_completed: bool = False,
    assets: Optional[List[str]] = None,
    assets_other: Optional[str] = None,
    vehicle_number: Optional[str] = None,
    vehicle_type: Optional[str] = None,
) -> Dict[str, Any]:
    _require_create(ctx)
    _require_site(ctx, location_id)

    if not policy_accepted:
        raise InvitationError("policy_required", "Visitor policy must be accepted.")

    location = db.query(Location).filter(Location.id == location_id, Location.is_active.is_(True)).first()
    if not location:
        raise InvitationError("invalid_location", "Selected location is not available.")

    scheduled_start = parse_scheduled_start(visit_date, arrival_time, location.timezone)
    now = datetime.now(timezone.utc)
    if scheduled_start < now - timedelta(minutes=5):
        raise InvitationError("invalid_schedule", "Visit date cannot be in the past.")

    if departure_time:
        scheduled_end = parse_scheduled_start(visit_date, departure_time, location.timezone)
        if scheduled_end <= scheduled_start:
            raise InvitationError("invalid_schedule", "Expected departure must be after arrival.")
        expected_duration_minutes = int((scheduled_end - scheduled_start).total_seconds() / 60)
        if expected_duration_minutes <= 0:
            raise InvitationError("invalid_schedule", "Invalid arrival and departure times.")
    else:
        if expected_duration_minutes not in ALLOWED_DURATIONS:
            raise InvitationError("invalid_duration", "Please select a valid expected duration.")
        scheduled_end = scheduled_start + timedelta(minutes=expected_duration_minutes)

    purpose = purpose.strip()
    if len(purpose) < 2 or len(purpose) > 500:
        raise InvitationError("invalid_purpose", "Please enter a visit purpose.")

    if notes:
        notes = notes.strip()
        if len(notes) > MAX_NOTES_LENGTH:
            raise InvitationError("invalid_notes", "Notes are too long.")

    try:
        visitor_type = validate_visitor_type(db, visitor_type_code)
    except RegistrationError as exc:
        raise InvitationError(exc.code, exc.message)

    from app.application.register_visitor_policy import (
        get_register_visitor_policy,
        validate_register_fields,
    )

    policy = get_register_visitor_policy(visitor_type)
    validate_register_fields(
        policy,
        email=email,
        company=company,
        host_id=host_id,
        govt_id_type=govt_id_type,
        govt_id_number=govt_id_number,
        signature_storage_key=signature_storage_key,
        work_purpose=work_purpose,
        po_work_order_reference=po_work_order_reference,
        safety_acknowledged=safety_acknowledged,
        safety_induction_completed=safety_induction_completed,
    )

    host = None
    if host_id:
        try:
            host = validate_host_for_site(db, host_id, location_id)
        except RegistrationError as exc:
            raise InvitationError(exc.code, exc.message)

    company_stripped = (company or "").strip()
    vendor_row: Optional[VendorCompany] = None
    if visitor_type.requires_vendor_compliance:
        resolved_vendor_id = vendor_company_id
        if resolved_vendor_id:
            vendor_row = (
                db.query(VendorCompany).filter(VendorCompany.id == resolved_vendor_id).first()
            )
            if not vendor_row or not vendor_row.is_active:
                raise InvitationError("invalid_vendor", "Vendor company not found or inactive.")
            assignment = (
                db.query(VendorCompanyLocation)
                .filter(
                    VendorCompanyLocation.vendor_company_id == resolved_vendor_id,
                    VendorCompanyLocation.location_id == location_id,
                    VendorCompanyLocation.is_active.is_(True),
                )
                .first()
            )
            if not assignment:
                raise InvitationError("vendor_location", "Vendor company is not assigned to this location.")
        elif company_stripped:
            candidate = (
                db.query(VendorCompany)
                .filter(
                    func.lower(VendorCompany.name) == company_stripped.lower(),
                    VendorCompany.is_active.is_(True),
                )
                .first()
            )
            if candidate:
                assignment = (
                    db.query(VendorCompanyLocation)
                    .filter(
                        VendorCompanyLocation.vendor_company_id == candidate.id,
                        VendorCompanyLocation.location_id == location_id,
                        VendorCompanyLocation.is_active.is_(True),
                    )
                    .first()
                )
                if assignment:
                    vendor_row = candidate
                    resolved_vendor_id = candidate.id
        vendor_company_id = resolved_vendor_id

    full_name = normalize_name(full_name)
    normalized_mobile = validate_indian_mobile(mobile)
    normalized_email = normalize_email(email) if email and email.strip() else None
    company_val = company_stripped
    if vendor_row:
        company_val = company_val or vendor_row.name

    audit = AuditService(db)
    visitor, _ = find_or_create_visitor(
        db,
        full_name,
        normalized_mobile,
        normalized_email or "",
        company_val,
        visitor_type.id,
        audit,
        designation=designation,
        address=address,
    )

    registration_meta = _build_registration_metadata(
        govt_id_type,
        govt_id_number,
        photo_storage_key,
        signature_storage_key,
        id_image_storage_key,
        nda_signed,
        ppe_required,
        safety_induction_completed,
        assets,
        assets_other,
        vehicle_number,
        vehicle_type,
        departure_time,
        vendor_company_id,
        po_work_order_reference,
    )

    reference = generate_registration_reference(db)

    visit = Visit(
        visitor_id=visitor.id,
        location_id=location_id,
        status=VisitStatus.PENDING_APPROVAL.value,
        registration_reference=reference,
        host_id=host.id if host else None,
        host_name=host.name if host else None,
        purpose=purpose,
        notes=notes,
        expected_duration_minutes=expected_duration_minutes,
        expected_arrival=scheduled_start,
        scheduled_start=scheduled_start,
        scheduled_end=scheduled_end,
        policy_accepted=True,
        policy_accepted_at=now,
        policy_version=CURRENT_POLICY_VERSION,
        source=VisitSource.ADVANCE_REGISTRATION.value,
        created_by_user_id=ctx.user_id,
        invitation_active=False,
        registration_metadata_json=registration_meta,
    )
    db.add(visit)
    db.flush()

    if photo_media_id:
        staged = (
            db.query(VisitorMedia)
            .filter(
                VisitorMedia.id == photo_media_id,
                VisitorMedia.media_type == "VISITOR_PHOTO",
                VisitorMedia.status == "STAGED",
            )
            .first()
        )
        if not staged or staged.created_by_user_id != ctx.user_id:
            raise InvitationError("invalid_photo", "Staged visitor photo is invalid or expired.")
        from app.application.visitor_media_service import finalize_visitor_photo
        photo_final = finalize_visitor_photo(
            db,
            photo_media_id,
            visitor.id,
            visit.id,
            location_id,
            reference,
            full_name,
        )
        if photo_final and visit.registration_metadata_json is not None:
            meta = dict(visit.registration_metadata_json)
            meta["photo_media_id"] = photo_media_id
            meta["photo_display_filename"] = photo_final.get("display_filename")
            visit.registration_metadata_json = meta

    if visitor_type.requires_vendor_compliance and vendor_company_id:
        profile = (
            db.query(VendorVisitorProfile)
            .filter(
                VendorVisitorProfile.visitor_id == visitor.id,
                VendorVisitorProfile.vendor_company_id == vendor_company_id,
            )
            .first()
        )
        if not profile:
            db.add(
                VendorVisitorProfile(
                    visitor_id=visitor.id,
                    vendor_company_id=vendor_company_id,
                    is_active=True,
                )
            )
        work = (work_purpose or purpose).strip()
        db.add(
            VendorVisitDetails(
                visit_id=visit.id,
                vendor_company_id=vendor_company_id,
                work_purpose=work,
                po_work_order_reference=(po_work_order_reference or "").strip() or None,
                safety_acknowledged=safety_acknowledged or safety_induction_completed,
            )
        )

    audit.record(
        action="ADVANCE_VISIT_CREATED",
        entity_type="visit",
        entity_id=str(visit.id),
        actor_id=ctx.user_id,
        actor_email=ctx.email,
        location_id=location_id,
        after_value={
            "reference": reference,
            "status": VisitStatus.PENDING_APPROVAL.value,
            "scheduled_start": scheduled_start.isoformat(),
            "policy_version": CURRENT_POLICY_VERSION,
        },
    )

    if policy_accepted:
        audit.record(
            action="POLICY_ACCEPTED",
            entity_type="visit",
            entity_id=str(visit.id),
            actor_id=ctx.user_id,
            actor_email=ctx.email,
            location_id=location_id,
            after_value={"policy_version": CURRENT_POLICY_VERSION, "source": "staff_registration"},
        )

    from app.application.host_approval_service import maybe_create_for_pending_visit
    maybe_create_for_pending_visit(db, visit.id)

    from app.application.security_screening_service import screen_visit
    screen_visit(db, visit.id, trigger="advance_registration")

    from app.application.compliance_service import evaluate_visit_compliance
    evaluate_visit_compliance(db, visit.id, trigger="advance_registration")

    db.commit()

    from app.application.notification_dispatch_service import dispatch_pending_notifications
    dispatch_pending_notifications(db)

    return _build_invitation_dict(db, _load_visit(db, visit.id) or visit)


def activate_invitation(db: Session, visit_id: int) -> None:
    visit = _load_visit(db, visit_id)
    if not visit or visit.source != VisitSource.ADVANCE_REGISTRATION.value:
        return
    if visit.status != VisitStatus.APPROVED.value:
        return

    if not visit.scheduled_start or not visit.scheduled_end:
        return

    early = timedelta(minutes=settings.invitation_early_arrival_minutes)
    grace = timedelta(minutes=settings.invitation_late_grace_minutes)
    valid_from = visit.scheduled_start - early
    valid_until = visit.scheduled_end + grace

    if not visit.invitation_token:
        for _ in range(10):
            token = generate_invitation_token()
            exists = db.query(Visit.id).filter(Visit.invitation_token == token).first()
            if not exists:
                visit.invitation_token = token
                break
        else:
            raise InvitationError("token_generation_failed", "Unable to generate invitation token.", 500)

    visit.invitation_valid_from = valid_from
    visit.invitation_valid_until = valid_until
    visit.invitation_active = True

    audit = AuditService(db)
    audit.record(
        action="INVITATION_ACTIVATED",
        entity_type="visit",
        entity_id=str(visit.id),
        location_id=visit.location_id,
        after_value={"valid_from": valid_from.isoformat(), "valid_until": valid_until.isoformat()},
    )

    _queue_visitor_invitation_notification(db, visit, valid_until)


def list_invitations(
    db: Session,
    ctx: AuthContext,
    tab: Optional[str] = None,
    search: Optional[str] = None,
    site: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[List[Dict[str, Any]], int]:
    _require_read(ctx)

    query = (
        db.query(Visit)
        .options(
            joinedload(Visit.visitor).joinedload(Visitor.visitor_type),
            joinedload(Visit.location),
            joinedload(Visit.approvals),
        )
        .filter(Visit.source == VisitSource.ADVANCE_REGISTRATION.value)
    )
    query = apply_location_scope(query, ctx, db, site)

    tab_key = (tab or "UPCOMING").upper()
    now = datetime.now(timezone.utc)

    if tab_key == "PENDING_APPROVAL":
        query = query.filter(Visit.status == VisitStatus.PENDING_APPROVAL.value)
    elif tab_key == "APPROVED":
        query = query.filter(Visit.status == VisitStatus.APPROVED.value)
    elif tab_key == "COMPLETED":
        query = query.filter(Visit.status.in_([
            VisitStatus.CHECKED_OUT.value,
            VisitStatus.ONSITE.value,
            VisitStatus.ARRIVED.value,
            VisitStatus.CHECKED_IN.value,
        ]))
    elif tab_key == "CANCELLED":
        query = query.filter(Visit.status == VisitStatus.CANCELLED.value)
    elif tab_key == "UPCOMING":
        query = query.filter(
            Visit.scheduled_start.isnot(None),
            Visit.scheduled_start >= now,
            Visit.status.in_([
                VisitStatus.PENDING_APPROVAL.value,
                VisitStatus.APPROVED.value,
            ]),
        )
    # ALL - no extra filter

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.join(Visitor, Visit.visitor_id == Visitor.id)
        query = query.filter(
            or_(
                Visitor.full_name.ilike(term),
                Visitor.company.ilike(term),
                Visit.registration_reference.ilike(term),
                Visit.host_name.ilike(term),
            )
        )

    total = query.count()
    visits = query.order_by(Visit.scheduled_start.desc().nullslast(), Visit.created_at.desc()).offset(offset).limit(limit).all()
    return [_build_invitation_dict(db, v) for v in visits], total


def get_invitation_detail(db: Session, ctx: AuthContext, visit_id: int) -> Dict[str, Any]:
    _require_read(ctx)
    visit = _load_visit(db, visit_id)
    if not visit or visit.source != VisitSource.ADVANCE_REGISTRATION.value:
        raise InvitationError("not_found", "Invitation not found.", 404)
    _require_site(ctx, visit.location_id)
    return _build_invitation_dict(db, visit)


def get_invitation_qr_meta(db: Session, ctx: AuthContext, visit_id: int) -> Dict[str, Any]:
    detail = get_invitation_detail(db, ctx, visit_id)
    visit = _load_visit(db, visit_id)
    if not visit or not visit.invitation_token or not visit.invitation_active:
        raise InvitationError("invitation_not_active", "Invitation QR is not active for this visit.", 400)
    from app.core.config import settings as app_settings
    origin = app_settings.public_app_origin
    url = f"{origin}/visit/invitation/{visit.invitation_token}"
    return {
        **detail,
        "invitation_url": url,
    }


def cancel_invitation(
    db: Session,
    ctx: AuthContext,
    visit_id: int,
    reason: str,
) -> Dict[str, Any]:
    _require_cancel(ctx)
    visit = _load_visit(db, visit_id)
    if not visit or visit.source != VisitSource.ADVANCE_REGISTRATION.value:
        raise InvitationError("not_found", "Invitation not found.", 404)
    _require_site(ctx, visit.location_id)

    reason = reason.strip()
    if not reason or len(reason) > MAX_CANCEL_REASON_LENGTH:
        raise InvitationError("reason_required", "Cancellation reason is required.")

    if visit.status in (VisitStatus.ONSITE.value, VisitStatus.CHECKED_OUT.value, VisitStatus.CHECKED_IN.value):
        raise InvitationError("INVALID_VISIT_STATE", "Cannot cancel a visit that has already checked in.", 409)

    if visit.status == VisitStatus.CANCELLED.value:
        return _build_invitation_dict(db, visit)

    if visit.status not in (VisitStatus.PENDING_APPROVAL.value, VisitStatus.APPROVED.value):
        raise InvitationError("INVALID_VISIT_STATE", "This visit cannot be cancelled.", 409)

    validate_transition(VisitStatus(visit.status), VisitStatus.CANCELLED)
    now = datetime.now(timezone.utc)
    previous = visit.status
    visit.status = VisitStatus.CANCELLED.value
    visit.invitation_active = False
    visit.cancelled_at = now
    visit.cancelled_by_user_id = ctx.user_id
    visit.cancellation_reason = reason

    from app.application.host_approval_service import revoke_pending_requests
    from app.application.notification_service import cancel_pending_notifications_for_visit
    revoke_pending_requests(db, visit.id)
    cancel_pending_notifications_for_visit(db, visit.id, NotificationType.UPCOMING_VISIT_REMINDER.value)

    audit = AuditService(db)
    audit.record(
        action="VISIT_CANCELLED",
        entity_type="visit",
        entity_id=str(visit.id),
        actor_id=ctx.user_id,
        actor_email=ctx.email,
        location_id=visit.location_id,
        before_value={"status": previous},
        after_value={"status": VisitStatus.CANCELLED.value, "reason": reason[:100]},
    )

    db.commit()
    return _build_invitation_dict(db, _load_visit(db, visit_id) or visit)


def get_public_invitation(db: Session, token: str) -> Dict[str, Any]:
    visit = _load_by_token(db, token)
    if not visit:
        raise InvitationError("invalid_invitation", "This invitation link is invalid.", 404)

    if visit.status in (VisitStatus.REJECTED.value, VisitStatus.CANCELLED.value):
        raise InvitationError("invitation_invalid", "This visitor invitation is no longer active.", 400)

    if not visit.invitation_active:
        raise InvitationError("invitation_not_active", "This invitation is not yet active.", 400)

    inv_status = _invitation_status(visit)
    if inv_status == "EXPIRED":
        raise InvitationError("INVITATION_EXPIRED", "This invitation has expired.", 400)
    if inv_status == "NOT_YET_VALID":
        raise InvitationError("INVITATION_NOT_YET_VALID", "This invitation is not yet valid.", 400)

    visitor = visit.visitor
    location = visit.location
    return {
        "visitor_name": visitor.full_name if visitor else "",
        "company": visitor.company if visitor else None,
        "site_name": location.name if location else "",
        "site_city": location.city if location else None,
        "host_name": visit.host_name,
        "purpose": visit.purpose,
        "scheduled_start": visit.scheduled_start.isoformat() if visit.scheduled_start else None,
        "status": visit.status,
        "invitation_token": token,
    }
