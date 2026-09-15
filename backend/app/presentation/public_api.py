from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session, joinedload

from app.application.invitation_service import InvitationError, get_public_invitation
from app.application.rate_limit_service import (
    check_invitation_public_rate_limit,
    check_public_site_rate_limit,
    check_registration_rate_limit,
)

from app.application.registration_service import (
    CURRENT_POLICY_VERSION,
    RegistrationError,
    create_self_registration,
    get_location_by_token,
    get_location_by_token_any,
)
from app.core.errors import APIError
from app.domain.models import Host, HostLocationAssignment, Location, VisitorType
from app.infrastructure.database import get_db
from app.presentation.schemas import (
    PublicHostResponse,
    PublicInvitationResponse,
    PublicRegistrationRequest,
    PublicRegistrationResponse,
    PublicSiteResponse,
    PublicVisitorTypeResponse,
)

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/sites/{token}", response_model=PublicSiteResponse)
def get_public_site(
    token: str,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> PublicSiteResponse:
    check_public_site_rate_limit(request)
    location = get_location_by_token(db, token)
    if not location:
        raise APIError(404, "invalid_site", "This registration link is invalid or no longer active.")
    return PublicSiteResponse(name=location.name, registration_enabled=location.registration_enabled)


@router.get("/sites/{token}/hosts", response_model=list[PublicHostResponse])
def search_public_hosts(
    token: str,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    search: Annotated[str, Query(min_length=0, max_length=100)] = "",
) -> list[PublicHostResponse]:
    check_public_site_rate_limit(request)
    location = get_location_by_token(db, token)
    if not location:
        raise APIError(404, "invalid_site", "This registration link is invalid or no longer active.")

    query = (
        db.query(Host)
        .join(HostLocationAssignment, HostLocationAssignment.host_id == Host.id)
        .filter(
            HostLocationAssignment.location_id == location.id,
            Host.is_active.is_(True),
        )
    )
    if search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            (Host.name.ilike(term)) | (Host.department.ilike(term))
        )
    hosts = query.order_by(Host.name).limit(20).all()
    return [
        PublicHostResponse(id=h.id, name=h.name, department=h.department)
        for h in hosts
    ]


@router.get("/sites/{token}/visitor-types", response_model=list[PublicVisitorTypeResponse])
def list_public_visitor_types(
    token: str,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> list[PublicVisitorTypeResponse]:
    check_public_site_rate_limit(request)
    location = get_location_by_token(db, token)
    if not location:
        raise APIError(404, "invalid_site", "This registration link is invalid or no longer active.")

    types = db.query(VisitorType).filter(VisitorType.is_active.is_(True)).order_by(VisitorType.name).all()
    return [PublicVisitorTypeResponse(code=t.code, name=t.name) for t in types]


@router.get("/policy")
def get_visitor_policy() -> dict:
    return {
        "version": CURRENT_POLICY_VERSION,
        "title": "Visitor Policy",
        "content": (
            "By registering as a visitor, you agree to follow all site security and safety requirements. "
            "You must remain in authorized areas, follow instructions from site personnel, and comply with "
            "photography and device usage policies. Your host is responsible for your visit while on premises."
        ),
    }


@router.post("/registrations", response_model=PublicRegistrationResponse)
def submit_public_registration(
    body: PublicRegistrationRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> PublicRegistrationResponse:
    check_registration_rate_limit(request)
    try:
        result = create_self_registration(
            db=db,
            site_token=body.site_token,
            visitor_type_code=body.visitor_type,
            full_name=body.full_name,
            mobile=body.mobile,
            email=body.email,
            company=body.company,
            host_id=body.host_id,
            purpose=body.purpose,
            expected_duration_minutes=body.expected_duration_minutes,
            policy_accepted=body.policy_accepted,
        )
    except RegistrationError as exc:
        raise APIError(400, exc.code, exc.message)

    return PublicRegistrationResponse(**result)


@router.get("/invitations/{token}", response_model=PublicInvitationResponse)
def get_public_invitation_page(
    token: str,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> PublicInvitationResponse:
    check_invitation_public_rate_limit(request)
    try:
        data = get_public_invitation(db, token)
    except InvitationError as exc:
        raise APIError(exc.status_code, exc.code, exc.message)
    return PublicInvitationResponse(**data)
