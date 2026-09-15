from __future__ import annotations

from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.application.auth_service import AuthContext
from app.application.location_service import (
    LocationError,
    create_location,
    get_location_retire_summary,
    get_staff_counts_for_locations,
    retire_location,
    serialize_location,
)
from app.application.location_staff_service import (
    assign_location_staff,
    list_location_staff,
    remove_location_staff,
)
from app.application.site_scope_service import apply_location_scope, can_access_location
from app.application.registration_url_service import build_registration_public_url
from app.application.self_registration_qr_service import SelfRegistrationQrError, get_self_registration_qr_config
from app.core.errors import APIError
from app.domain.enums import Permission, VisitStatus
from app.domain.models import Host, HostLocationAssignment, Location, Visit, Visitor, VisitorType
from app.infrastructure.database import get_db
from app.presentation.dependencies import PermissionChecker
from app.presentation.schemas import (
    AddLocationStaffRequest,
    CreateLocationRequest,
    LocationRetireResponse,
    LocationRetireSummaryResponse,
    LocationResponse,
    LocationStaffMember,
    PublicHostResponse,
    PublicVisitorTypeResponse,
    SelfRegistrationDetail,
    SelfRegistrationItem,
    SelfRegistrationListResponse,
    SelfRegistrationQrConfigResponse,
)

router = APIRouter(tags=["admin"])


def _format_dt(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    return dt.isoformat()


def _build_registration_item(visit: Visit) -> SelfRegistrationItem:
    visitor = visit.visitor
    location = visit.location if hasattr(visit, "location") and visit.location else None
    visitor_type_name = None
    if visitor and visitor.visitor_type_id:
        vt = visitor.visitor_type if hasattr(visitor, "visitor_type") and visitor.visitor_type else None
        if vt:
            visitor_type_name = vt.name

    return SelfRegistrationItem(
        id=visit.id,
        registration_reference=visit.registration_reference,
        status=visit.status,
        visitor_name=visitor.full_name if visitor else "",
        visitor_mobile=visitor.phone if visitor else None,
        visitor_email=visitor.email if visitor else None,
        company=visitor.company if visitor else None,
        visitor_type=visitor_type_name,
        host_name=visit.host_name,
        site_name=location.name if location else "",
        site_id=visit.location_id,
        purpose=visit.purpose,
        expected_duration_minutes=visit.expected_duration_minutes,
        policy_accepted=visit.policy_accepted,
        submitted_at=_format_dt(visit.created_at) or "",
    )


@router.get("/self-registrations", response_model=SelfRegistrationListResponse)
def list_self_registrations(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(PermissionChecker(Permission.REGISTRATION_READ))],
    status: Annotated[Optional[str], Query()] = None,
    search: Annotated[Optional[str], Query(max_length=100)] = None,
    site: Annotated[Optional[int], Query()] = None,
    visitor_type: Annotated[Optional[str], Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SelfRegistrationListResponse:
    query = (
        db.query(Visit)
        .options(
            joinedload(Visit.visitor).joinedload(Visitor.visitor_type),
            joinedload(Visit.location),
        )
        .filter(Visit.source == "self_registration")
    )

    query = apply_location_scope(query, user, db, site)

    if status and status.upper() != "ALL":
        query = query.filter(Visit.status == status.upper())
    else:
        query = query.filter(Visit.status.in_([
            VisitStatus.PENDING_APPROVAL.value,
            VisitStatus.APPROVED.value,
            VisitStatus.REJECTED.value,
        ]))

    if visitor_type:
        query = query.join(Visitor).join(VisitorType).filter(VisitorType.code == visitor_type.upper())

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.join(Visitor, Visit.visitor_id == Visitor.id).filter(
            or_(
                Visitor.full_name.ilike(term),
                Visitor.email.ilike(term),
                Visitor.phone.ilike(term),
                Visit.registration_reference.ilike(term),
                Visit.host_name.ilike(term),
            )
        )

    total = query.count()
    visits = query.order_by(Visit.created_at.desc()).offset(offset).limit(limit).all()

    return SelfRegistrationListResponse(
        items=[_build_registration_item(v) for v in visits],
        total=total,
        limit=limit,
        offset=offset,
    )


def _registration_url(token: Optional[str]) -> Optional[str]:
    if not token:
        return None
    return build_registration_public_url(token)


@router.get("/self-registrations/qr-config", response_model=SelfRegistrationQrConfigResponse)
def get_self_registration_qr_config_endpoint(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(PermissionChecker(Permission.REGISTRATION_READ))],
    site: Annotated[Optional[int], Query()] = None,
) -> SelfRegistrationQrConfigResponse:
    try:
        payload = get_self_registration_qr_config(db, user, location_id=site)
        return SelfRegistrationQrConfigResponse(**payload)
    except SelfRegistrationQrError as exc:
        raise APIError(exc.status_code, exc.code, exc.message)


@router.get("/self-registrations/{registration_id}", response_model=SelfRegistrationDetail)
def get_self_registration(
    registration_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(PermissionChecker(Permission.REGISTRATION_READ))],
) -> SelfRegistrationDetail:
    visit = (
        db.query(Visit)
        .options(
            joinedload(Visit.visitor).joinedload(Visitor.visitor_type),
            joinedload(Visit.location),
        )
        .filter(Visit.id == registration_id, Visit.source == "self_registration")
        .first()
    )
    if not visit:
        raise APIError(404, "not_found", "Registration not found.")

    if not can_access_location(user, visit.location_id):
        raise APIError(403, "forbidden", "You do not have access to this registration.")

    item = _build_registration_item(visit)
    return SelfRegistrationDetail(
        **item.model_dump(),
        policy_version=visit.policy_version,
        policy_accepted_at=_format_dt(visit.policy_accepted_at),
    )


@router.get("/locations", response_model=list[LocationResponse])
def list_locations(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(PermissionChecker(Permission.LOCATIONS_READ))],
) -> list[LocationResponse]:
    query = db.query(Location).filter(Location.is_active.is_(True))
    if user.role.value in ("SITE_ADMIN", "SECURITY") and user.location_ids:
        query = query.filter(Location.id.in_(user.location_ids))
    locations = query.order_by(Location.name).all()
    can_view_token = Permission.LOCATIONS_MANAGE in user.permissions or user.role.value in ("GLOBAL_ADMIN", "HEAD_ADMIN", "SITE_ADMIN")
    location_ids = [loc.id for loc in locations]
    staff_counts = get_staff_counts_for_locations(db, location_ids)
    return [
        LocationResponse(**serialize_location(
            loc,
            include_token=can_view_token,
            staff_counts=staff_counts.get(loc.id),
        ))
        for loc in locations
    ]


@router.post("/locations", response_model=LocationResponse, status_code=201)
def post_location(
    payload: CreateLocationRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(PermissionChecker(Permission.LOCATIONS_MANAGE))],
) -> LocationResponse:
    try:
        data = create_location(
            db,
            user,
            name=payload.name,
            code=payload.code,
            timezone=payload.timezone,
            registration_enabled=payload.registration_enabled,
        )
        db.commit()
        return LocationResponse(**data)
    except LocationError as exc:
        db.rollback()
        raise APIError(exc.status_code, exc.code, exc.message)


@router.get("/locations/{location_id}/staff", response_model=list[LocationStaffMember])
def get_location_staff(
    location_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(PermissionChecker(Permission.LOCATIONS_MANAGE))],
) -> list[LocationStaffMember]:
    try:
        rows = list_location_staff(db, user, location_id)
        return [LocationStaffMember(**row) for row in rows]
    except LocationError as exc:
        raise APIError(exc.status_code, exc.code, exc.message)


@router.post("/locations/{location_id}/staff", response_model=LocationStaffMember, status_code=201)
def post_location_staff(
    location_id: int,
    payload: AddLocationStaffRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(PermissionChecker(Permission.LOCATIONS_MANAGE))],
) -> LocationStaffMember:
    try:
        data = assign_location_staff(
            db,
            user,
            location_id,
            email=payload.email,
            display_name=payload.display_name,
            role=payload.role,
        )
        db.commit()
        return LocationStaffMember(**data)
    except LocationError as exc:
        db.rollback()
        raise APIError(exc.status_code, exc.code, exc.message)


@router.delete("/locations/{location_id}/staff/{user_id}", status_code=204, response_class=Response)
def delete_location_staff(
    location_id: int,
    user_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(PermissionChecker(Permission.LOCATIONS_MANAGE))],
) -> Response:
    try:
        remove_location_staff(db, user, location_id, user_id)
        db.commit()
        return Response(status_code=204)
    except LocationError as exc:
        db.rollback()
        raise APIError(exc.status_code, exc.code, exc.message)


@router.get("/locations/{location_id}/retire-summary", response_model=LocationRetireSummaryResponse)
def get_location_retire_summary_endpoint(
    location_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(PermissionChecker(Permission.LOCATIONS_MANAGE))],
) -> LocationRetireSummaryResponse:
    try:
        data = get_location_retire_summary(db, user, location_id)
        return LocationRetireSummaryResponse(**data)
    except LocationError as exc:
        raise APIError(exc.status_code, exc.code, exc.message)


@router.delete("/locations/{location_id}", response_model=LocationRetireResponse)
def delete_location_endpoint(
    location_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(PermissionChecker(Permission.LOCATIONS_MANAGE))],
    reason: Annotated[Optional[str], Query(max_length=500)] = None,
) -> LocationRetireResponse:
    try:
        data = retire_location(db, user, location_id, reason=reason)
        db.commit()
        return LocationRetireResponse(**data)
    except LocationError as exc:
        db.rollback()
        raise APIError(exc.status_code, exc.code, exc.message)


@router.get("/visitor-types", response_model=list[PublicVisitorTypeResponse])
def list_visitor_types(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(PermissionChecker(Permission.INVITATION_CREATE))],
) -> list[PublicVisitorTypeResponse]:
    types = db.query(VisitorType).filter(VisitorType.is_active.is_(True)).order_by(VisitorType.name).all()
    return [PublicVisitorTypeResponse(
        code=t.code,
        name=t.name,
        requires_vendor_compliance=t.requires_vendor_compliance,
        po_reference_required=t.po_reference_required,
    ) for t in types]


@router.get("/locations/{location_id}/hosts", response_model=list[PublicHostResponse])
def list_location_hosts(
    location_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(PermissionChecker(Permission.INVITATION_CREATE))],
    search: Annotated[str, Query(max_length=100)] = "",
) -> list[PublicHostResponse]:
    if not can_access_location(user, location_id):
        raise APIError(403, "forbidden", "You do not have access to this location.")

    query = (
        db.query(Host)
        .join(HostLocationAssignment, HostLocationAssignment.host_id == Host.id)
        .filter(
            HostLocationAssignment.location_id == location_id,
            Host.is_active.is_(True),
        )
    )
    if search.strip():
        term = f"%{search.strip()}%"
        query = query.filter((Host.name.ilike(term)) | (Host.department.ilike(term)))
    hosts = query.order_by(Host.name).limit(50).all()
    return [PublicHostResponse(id=h.id, name=h.name, department=h.department, email=h.email) for h in hosts]
