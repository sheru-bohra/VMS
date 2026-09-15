from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.application.approval_service import (
    ApprovalError,
    approve_visit,
    get_approval_detail,
    list_approvals,
    reject_visit,
)
from app.application.auth_service import AuthContext
from app.core.errors import APIError
from app.domain.enums import REJECTION_REASON_LABELS, RejectionReason
from app.infrastructure.database import get_db
from app.presentation.dependencies import require_auth
from app.presentation.schemas import (
    ApprovalListResponse,
    ApprovalQueueItem,
    ApproveRequest,
    RejectRequest,
    RejectionReasonOption,
)

router = APIRouter(tags=["approvals"])


def _handle_approval_error(exc: ApprovalError) -> None:
    raise APIError(exc.status_code, exc.code, exc.message)


@router.get("/approvals/rejection-reasons", response_model=list[RejectionReasonOption])
def get_rejection_reasons(
    _user: Annotated[AuthContext, Depends(require_auth)],
) -> list[RejectionReasonOption]:
    return [
        RejectionReasonOption(code=r.value, label=REJECTION_REASON_LABELS[r])
        for r in RejectionReason
    ]


@router.get("/approvals", response_model=ApprovalListResponse)
def list_approval_queue(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
    status: Annotated[Optional[str], Query()] = None,
    search: Annotated[Optional[str], Query(max_length=100)] = None,
    site: Annotated[Optional[int], Query()] = None,
    visitor_type: Annotated[Optional[str], Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ApprovalListResponse:
    try:
        items, total, pending_count = list_approvals(
            db, user, status=status, search=search, site=site,
            visitor_type=visitor_type, limit=limit, offset=offset,
        )
    except ApprovalError as exc:
        _handle_approval_error(exc)
    return ApprovalListResponse(
        items=[ApprovalQueueItem(**item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
        pending_count=pending_count,
    )


@router.get("/approvals/{visit_id}", response_model=ApprovalQueueItem)
def get_approval(
    visit_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
) -> ApprovalQueueItem:
    try:
        detail = get_approval_detail(db, user, visit_id)
    except ApprovalError as exc:
        _handle_approval_error(exc)
    return ApprovalQueueItem(**detail)


@router.post("/approvals/{visit_id}/approve", response_model=ApprovalQueueItem)
def approve_registration(
    visit_id: int,
    body: ApproveRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
) -> ApprovalQueueItem:
    try:
        detail = approve_visit(db, user, visit_id, comment=body.comment)
    except ApprovalError as exc:
        _handle_approval_error(exc)
    return ApprovalQueueItem(**detail)


@router.post("/approvals/{visit_id}/reject", response_model=ApprovalQueueItem)
def reject_registration(
    visit_id: int,
    body: RejectRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
) -> ApprovalQueueItem:
    try:
        detail = reject_visit(db, user, visit_id, reason_code=body.reason_code, comment=body.comment)
    except ApprovalError as exc:
        _handle_approval_error(exc)
    return ApprovalQueueItem(**detail)


@router.post("/approvals/{visit_id}/resend-host-approval")
def resend_host_approval_endpoint(
    visit_id: int,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthContext, Depends(require_auth)],
):
    from app.application.host_approval_service import HostApprovalError, resend_host_approval

    try:
        result = resend_host_approval(db, visit_id, user.user_id, user.email)
    except HostApprovalError as exc:
        raise APIError(exc.status_code, exc.code, exc.message)
    return result
