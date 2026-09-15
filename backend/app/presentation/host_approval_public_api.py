from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.application.host_approval_service import HostApprovalError, get_public_host_approval_summary, host_approve, host_reject
from app.application.rate_limit_service import check_host_approval_rate_limit
from app.core.errors import APIError
from app.domain.enums import HOST_REJECTION_REASONS, REJECTION_REASON_LABELS
from app.infrastructure.database import get_db
from app.presentation.schemas import (
    HostApprovalActionResponse,
    HostApprovalPublicResponse,
    HostRejectionReasonOption,
)

router = APIRouter(tags=["host-approval-public"])


def _handle(exc: HostApprovalError) -> None:
    raise APIError(exc.status_code, exc.code, exc.message)


class HostApproveBody(BaseModel):
    token: str = Field(..., min_length=16)


class HostRejectBody(BaseModel):
    token: str = Field(..., min_length=16)
    reason_code: str = Field(..., min_length=1, max_length=50)
    comment: Optional[str] = Field(None, max_length=500)


@router.get("/public/host-approvals/rejection-reasons", response_model=list[HostRejectionReasonOption])
def get_host_rejection_reasons() -> list[HostRejectionReasonOption]:
    return [
        HostRejectionReasonOption(code=r.value, label=REJECTION_REASON_LABELS[r])
        for r in HOST_REJECTION_REASONS
    ]


@router.get("/public/host-approvals/{token}", response_model=HostApprovalPublicResponse)
def get_host_approval_page(
    token: str,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> HostApprovalPublicResponse:
    check_host_approval_rate_limit(request)
    try:
        data = get_public_host_approval_summary(db, token)
    except HostApprovalError as exc:
        _handle(exc)
    return HostApprovalPublicResponse(**data)


@router.post("/public/host-approvals/approve", response_model=HostApprovalActionResponse)
def post_host_approve(
    body: HostApproveBody,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> HostApprovalActionResponse:
    check_host_approval_rate_limit(request)
    try:
        result = host_approve(db, body.token)
    except HostApprovalError as exc:
        _handle(exc)
    return HostApprovalActionResponse(**result)


@router.post("/public/host-approvals/reject", response_model=HostApprovalActionResponse)
def post_host_reject(
    body: HostRejectBody,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> HostApprovalActionResponse:
    check_host_approval_rate_limit(request)
    try:
        result = host_reject(db, body.token, body.reason_code, body.comment)
    except HostApprovalError as exc:
        _handle(exc)
    return HostApprovalActionResponse(**result)
