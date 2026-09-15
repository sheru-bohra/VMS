"""Physical integration REST APIs."""

from __future__ import annotations

from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.application.access_config_service import (
    AccessConfigError,
    create_printer,
    create_profile,
    create_profile_mapping,
    deactivate_printer,
    deactivate_profile,
    deactivate_profile_mapping,
    get_printer,
    get_profile,
    list_location_configs,
    list_printers,
    list_profile_mappings,
    list_profiles,
    set_default_printer,
    update_location_config,
    update_printer,
    update_profile,
    update_profile_mapping,
)
from app.application.access_attention_service import list_attention_items
from app.application.access_control_provider import get_access_control_provider
from app.application.access_provisioning_service import (
    AccessProvisioningError,
    get_credential,
    list_credentials,
    retry_credential,
    revoke_credential_manual,
)
from app.application.auth_service import AuthContext
from app.application.badge_printer_provider import get_badge_printer_provider
from app.application.physical_badge_print_service import (
    PhysicalBadgePrintError,
    list_print_jobs,
    request_physical_print,
    retry_print_job,
)
from app.application.site_scope_service import can_access_location
from app.core.config import settings
from app.core.errors import APIError
from app.domain.enums import Permission
from app.infrastructure.database import get_db
from app.presentation.dependencies import PermissionChecker, require_auth
from app.domain.models import BadgePrinter, LocationAccessConfiguration

router = APIRouter(tags=["physical-integrations"])


def _access_err(exc: AccessProvisioningError) -> None:
    raise APIError(exc.status_code, exc.code, exc.message)


def _config_err(exc: AccessConfigError) -> None:
    raise APIError(exc.status_code, exc.code, exc.message)


def _print_err(exc: PhysicalBadgePrintError) -> None:
    raise APIError(exc.status_code, exc.code, exc.message)


class LocationConfigPatch(BaseModel):
    access_control_enabled: Optional[bool] = None
    provider_key: Optional[str] = None
    default_access_profile_id: Optional[int] = None
    credential_grace_minutes: Optional[int] = Field(None, ge=0, le=1440)
    max_credential_duration_minutes: Optional[int] = Field(None, ge=15, le=10080)
    is_active: Optional[bool] = None


class CreateProfileRequest(BaseModel):
    location_id: int
    name: str = Field(..., min_length=1, max_length=120)
    provider_external_profile_ref: str = Field(..., min_length=1, max_length=128)
    description: Optional[str] = Field(None, max_length=500)


class UpdateProfileRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    description: Optional[str] = Field(None, max_length=500)
    provider_external_profile_ref: Optional[str] = Field(None, min_length=1, max_length=128)


class CreateMappingRequest(BaseModel):
    location_id: int
    visitor_type_id: int
    access_profile_id: int


class CreatePrinterRequest(BaseModel):
    location_id: int
    name: str = Field(..., min_length=1, max_length=120)
    provider_key: str = Field(..., min_length=1, max_length=64)
    provider_external_printer_ref: str = Field(..., min_length=1, max_length=128)
    is_default: bool = False


class UpdatePrinterRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    provider_external_printer_ref: Optional[str] = Field(None, min_length=1, max_length=128)
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None


class UpdateMappingRequest(BaseModel):
    access_profile_id: int


@router.get("/access/attention")
def get_attention_items(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(PermissionChecker(Permission.ACCESS_READ))],
):
    return list_attention_items(db, user)


class PhysicalPrintRequest(BaseModel):
    printer_id: Optional[int] = None
    idempotency_key: Optional[str] = None


def _provider_label(key: str) -> str:
    if key == "dev_mock":
        return "DEVELOPMENT_ONLY"
    if key == "disabled":
        return "DISABLED"
    return key


@router.get("/access/credentials")
def get_credentials(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(PermissionChecker(Permission.ACCESS_READ))],
    status: Optional[str] = None,
    attention: bool = False,
):
    try:
        return list_credentials(db, user, status_filter=status, attention_only=attention)
    except AccessProvisioningError as exc:
        _access_err(exc)


@router.get("/access/credentials/{credential_id}")
def get_credential_detail(
    credential_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(PermissionChecker(Permission.ACCESS_READ))],
):
    try:
        return get_credential(db, user, credential_id)
    except AccessProvisioningError as exc:
        _access_err(exc)


@router.post("/access/credentials/{credential_id}/retry")
def post_retry_credential(
    credential_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(PermissionChecker(Permission.ACCESS_RETRY))],
):
    try:
        result = retry_credential(db, user, credential_id)
        db.commit()
        return result
    except AccessProvisioningError as exc:
        db.rollback()
        _access_err(exc)


@router.post("/access/credentials/{credential_id}/revoke")
def post_revoke_credential(
    credential_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(PermissionChecker(Permission.ACCESS_REVOKE))],
):
    try:
        result = revoke_credential_manual(db, user, credential_id)
        db.commit()
        return result
    except AccessProvisioningError as exc:
        db.rollback()
        _access_err(exc)


@router.get("/badge-print-jobs")
def get_print_jobs(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(PermissionChecker(Permission.BADGE_PRINTER_READ))],
    attention: bool = False,
):
    try:
        return list_print_jobs(db, user, attention_only=attention)
    except PhysicalBadgePrintError as exc:
        _print_err(exc)


@router.post("/badge-print-jobs/{job_id}/retry")
def post_retry_print_job(
    job_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(PermissionChecker(Permission.BADGE_PRINTER_OPERATE))],
):
    try:
        result = retry_print_job(db, user, job_id)
        db.commit()
        return result
    except PhysicalBadgePrintError as exc:
        db.rollback()
        _print_err(exc)


@router.post("/badges/visits/{visit_id}/physical-print")
def post_physical_print(
    visit_id: int,
    body: PhysicalPrintRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(PermissionChecker(Permission.BADGE_PRINTER_OPERATE))],
):
    try:
        result = request_physical_print(
            db, user, visit_id, printer_id=body.printer_id, idempotency_key=body.idempotency_key,
        )
        db.commit()
        return result
    except PhysicalBadgePrintError as exc:
        db.rollback()
        _print_err(exc)


@router.get("/physical-integrations/status")
def integration_status(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
):
    locations = []
    configs = db.query(LocationAccessConfiguration).all()
    for cfg in configs:
        if not can_access_location(user, cfg.location_id):
            continue
        ac_provider = get_access_control_provider(cfg.provider_key if cfg.access_control_enabled else "disabled")
        ac_health = ac_provider.health_check()
        printers = db.query(BadgePrinter).filter(BadgePrinter.location_id == cfg.location_id, BadgePrinter.is_active.is_(True)).all()
        printer_statuses = []
        for pr in printers:
            bp = get_badge_printer_provider(pr.provider_key)
            ph = bp.health_check(pr.provider_external_printer_ref)
            printer_statuses.append({
                "printer_id": pr.id,
                "name": pr.name,
                "status": ph.get("status"),
                "is_default": pr.is_default,
            })
        locations.append({
            "location_id": cfg.location_id,
            "access_control_enabled": cfg.access_control_enabled,
            "access_provider": cfg.provider_key,
            "access_provider_label": _provider_label(cfg.provider_key or "disabled"),
            "access_health": ac_health.get("status"),
            "printers": printer_statuses,
        })
    return {
        "access_control_enabled": settings.access_control_enabled,
        "badge_printer_enabled": settings.badge_printer_enabled,
        "access_provider": settings.access_control_provider,
        "access_provider_label": _provider_label(settings.access_control_provider),
        "badge_printer_provider": settings.badge_printer_provider,
        "badge_printer_provider_label": _provider_label(settings.badge_printer_provider),
        "locations": locations,
    }


@router.get("/access/config/locations")
def get_location_configs(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(PermissionChecker(Permission.ACCESS_CONFIG_READ))],
):
    try:
        return list_location_configs(db, user)
    except AccessConfigError as exc:
        _config_err(exc)


@router.patch("/access/config/locations/{location_id}")
def patch_location_config(
    location_id: int,
    body: LocationConfigPatch,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(PermissionChecker(Permission.ACCESS_CONFIG_MANAGE))],
):
    try:
        result = update_location_config(db, user, location_id, **body.model_dump(exclude_unset=True))
        db.commit()
        return result
    except AccessConfigError as exc:
        db.rollback()
        _config_err(exc)


@router.get("/access/profiles")
def get_profiles(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(PermissionChecker(Permission.ACCESS_CONFIG_READ))],
    location_id: Optional[int] = None,
):
    try:
        return list_profiles(db, user, location_id)
    except AccessConfigError as exc:
        _config_err(exc)


@router.post("/access/profiles")
def post_profile(
    body: CreateProfileRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(PermissionChecker(Permission.ACCESS_CONFIG_MANAGE))],
):
    try:
        result = create_profile(
            db, user, body.location_id, body.name, body.provider_external_profile_ref, body.description,
        )
        db.commit()
        return result
    except AccessConfigError as exc:
        db.rollback()
        _config_err(exc)


@router.get("/access/profiles/{profile_id}")
def get_profile_detail(
    profile_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(PermissionChecker(Permission.ACCESS_CONFIG_READ))],
):
    try:
        return get_profile(db, user, profile_id)
    except AccessConfigError as exc:
        _config_err(exc)


@router.patch("/access/profiles/{profile_id}")
def patch_profile(
    profile_id: int,
    body: UpdateProfileRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(PermissionChecker(Permission.ACCESS_CONFIG_MANAGE))],
):
    try:
        result = update_profile(db, user, profile_id, **body.model_dump(exclude_unset=True))
        db.commit()
        return result
    except AccessConfigError as exc:
        db.rollback()
        _config_err(exc)


@router.post("/access/profiles/{profile_id}/deactivate")
def post_deactivate_profile(
    profile_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(PermissionChecker(Permission.ACCESS_CONFIG_MANAGE))],
):
    try:
        result = deactivate_profile(db, user, profile_id)
        db.commit()
        return result
    except AccessConfigError as exc:
        db.rollback()
        _config_err(exc)


@router.get("/access/profile-mappings")
def get_mappings(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(PermissionChecker(Permission.ACCESS_CONFIG_READ))],
    location_id: Optional[int] = None,
):
    try:
        return list_profile_mappings(db, user, location_id)
    except AccessConfigError as exc:
        _config_err(exc)


@router.post("/access/profile-mappings")
def post_mapping(
    body: CreateMappingRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(PermissionChecker(Permission.ACCESS_CONFIG_MANAGE))],
):
    try:
        result = create_profile_mapping(
            db, user, body.location_id, body.visitor_type_id, body.access_profile_id,
        )
        db.commit()
        return result
    except AccessConfigError as exc:
        db.rollback()
        _config_err(exc)


@router.patch("/access/profile-mappings/{mapping_id}")
def patch_mapping(
    mapping_id: int,
    body: UpdateMappingRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(PermissionChecker(Permission.ACCESS_CONFIG_MANAGE))],
):
    try:
        result = update_profile_mapping(db, user, mapping_id, body.access_profile_id)
        db.commit()
        return result
    except AccessConfigError as exc:
        db.rollback()
        _config_err(exc)


@router.post("/access/profile-mappings/{mapping_id}/deactivate")
def post_deactivate_mapping(
    mapping_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(PermissionChecker(Permission.ACCESS_CONFIG_MANAGE))],
):
    try:
        result = deactivate_profile_mapping(db, user, mapping_id)
        db.commit()
        return result
    except AccessConfigError as exc:
        db.rollback()
        _config_err(exc)


@router.get("/badge-printers/{printer_id}")
def get_printer_detail(
    printer_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(PermissionChecker(Permission.BADGE_PRINTER_READ))],
):
    try:
        return get_printer(db, user, printer_id)
    except AccessConfigError as exc:
        _config_err(exc)


@router.patch("/badge-printers/{printer_id}")
def patch_printer(
    printer_id: int,
    body: UpdatePrinterRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(PermissionChecker(Permission.BADGE_PRINTER_CONFIG_MANAGE))],
):
    try:
        result = update_printer(db, user, printer_id, **body.model_dump(exclude_unset=True))
        db.commit()
        return result
    except AccessConfigError as exc:
        db.rollback()
        _config_err(exc)


@router.get("/badge-printers")
def get_printers(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(PermissionChecker(Permission.BADGE_PRINTER_READ))],
    location_id: Optional[int] = None,
):
    try:
        return list_printers(db, user, location_id)
    except AccessConfigError as exc:
        _config_err(exc)


@router.post("/badge-printers")
def post_printer(
    body: CreatePrinterRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(PermissionChecker(Permission.BADGE_PRINTER_CONFIG_MANAGE))],
):
    try:
        result = create_printer(
            db, user, body.location_id, body.name, body.provider_key,
            body.provider_external_printer_ref, body.is_default,
        )
        db.commit()
        return result
    except AccessConfigError as exc:
        db.rollback()
        _config_err(exc)


@router.post("/badge-printers/{printer_id}/set-default")
def post_set_default_printer(
    printer_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(PermissionChecker(Permission.BADGE_PRINTER_CONFIG_MANAGE))],
):
    try:
        result = set_default_printer(db, user, printer_id)
        db.commit()
        return result
    except AccessConfigError as exc:
        db.rollback()
        _config_err(exc)


@router.post("/badge-printers/{printer_id}/deactivate")
def post_deactivate_printer(
    printer_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(PermissionChecker(Permission.BADGE_PRINTER_CONFIG_MANAGE))],
):
    try:
        result = deactivate_printer(db, user, printer_id)
        db.commit()
        return result
    except AccessConfigError as exc:
        db.rollback()
        _config_err(exc)
