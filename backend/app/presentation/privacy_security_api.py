from __future__ import annotations

from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.application.audit_integrity_service import verify_chain
from app.application.auth_service import AuthContext
from app.application.data_retention_service import (
    RetentionError,
    create_policy,
    execute_policy,
    list_policies,
    preview_policy,
    RETENTION_CATEGORIES,
    RETENTION_ACTIONS,
)
from app.application.security_readiness_service import evaluate_readiness
from app.core.config import settings
from app.core.errors import APIError
from app.domain.enums import Permission
from app.infrastructure.database import get_db
from app.presentation.dependencies import PermissionChecker

router = APIRouter(prefix="/administration/privacy-security", tags=["privacy-security"])


class RetentionPolicyResponse(BaseModel):
    id: int
    data_category: str
    scope_type: str
    location_id: Optional[int] = None
    location_name: Optional[str] = None
    retention_days: int
    action: str
    is_active: bool


class CreateRetentionPolicyRequest(BaseModel):
    data_category: str
    scope_type: str = "GLOBAL"
    location_id: Optional[int] = None
    retention_days: int = Field(..., ge=1, le=3650)
    action: str


class ReadinessCheck(BaseModel):
    key: str
    label: str
    status: str
    detail: Optional[str] = None


class ReadinessResponse(BaseModel):
    ready: bool
    environment: str
    evaluated_at: str
    checks: List[ReadinessCheck]


class AuditIntegrityResponse(BaseModel):
    status: str
    sealed_count: int
    legacy_count: int
    last_verified_at: Optional[str] = None
    failed_sequence: Optional[int] = None
    failed_event_id: Optional[int] = None


def _retention_err(exc: RetentionError) -> None:
    raise APIError(exc.status_code, exc.code, exc.message)


@router.get("/retention/policies", response_model=List[RetentionPolicyResponse])
def get_retention_policies(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(PermissionChecker(Permission.PRIVACY_RETENTION_READ))],
):
    try:
        return list_policies(db, user)
    except RetentionError as exc:
        _retention_err(exc)


@router.post("/retention/policies", response_model=RetentionPolicyResponse)
def post_retention_policy(
    body: CreateRetentionPolicyRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(PermissionChecker(Permission.PRIVACY_RETENTION_MANAGE))],
):
    try:
        row = create_policy(
            db, user, body.data_category, body.scope_type, body.retention_days, body.action, body.location_id
        )
        db.commit()
        return row
    except RetentionError as exc:
        db.rollback()
        _retention_err(exc)


@router.get("/retention/policies/{policy_id}/preview")
def preview_retention_policy(
    policy_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(PermissionChecker(Permission.PRIVACY_RETENTION_READ))],
):
    try:
        result = preview_policy(db, user, policy_id)
        db.commit()
        return result
    except RetentionError as exc:
        db.rollback()
        _retention_err(exc)


@router.post("/retention/policies/{policy_id}/execute")
def execute_retention_policy(
    policy_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(PermissionChecker(Permission.PRIVACY_RETENTION_EXECUTE))],
):
    try:
        result = execute_policy(db, user, policy_id)
        db.commit()
        return result
    except RetentionError as exc:
        db.rollback()
        _retention_err(exc)


@router.get("/retention/meta")
def retention_meta(
    user: Annotated[AuthContext, Depends(PermissionChecker(Permission.PRIVACY_RETENTION_READ))],
):
    return {"categories": sorted(RETENTION_CATEGORIES), "actions": sorted(RETENTION_ACTIONS)}


@router.get("/readiness", response_model=ReadinessResponse)
def security_readiness(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(PermissionChecker(Permission.SECURITY_READINESS_READ))],
):
    return evaluate_readiness(db)


@router.get("/audit-integrity", response_model=AuditIntegrityResponse)
def audit_integrity_status(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(PermissionChecker(Permission.SECURITY_AUDIT_INTEGRITY_READ))],
):
    result = verify_chain(db)
    return AuditIntegrityResponse(**{k: result.get(k) for k in AuditIntegrityResponse.model_fields})


@router.post("/audit-integrity/verify", response_model=AuditIntegrityResponse)
def audit_integrity_verify(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(PermissionChecker(Permission.SECURITY_AUDIT_INTEGRITY_VERIFY))],
):
    return audit_integrity_status(db, user)


@router.get("/file-security")
def file_security_status(
    user: Annotated[AuthContext, Depends(PermissionChecker(Permission.SECURITY_READINESS_READ))],
):
    enc = bool(settings.document_encryption_key)
    return {
        "scanner_provider": settings.file_scanner_provider,
        "scanner_configured": settings.file_scanner_provider != "dev_noop" or not settings.is_production,
        "encryption_enabled": enc,
        "encryption_version": settings.document_encryption_version if enc else None,
    }
