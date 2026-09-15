from __future__ import annotations

from typing import Annotated, Any, Dict, List

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.application.auth_service import AuthContext
from app.application.operations_readiness_service import (
    build_operations_readiness,
    get_database_status,
    get_queue_status,
    get_scheduler_status,
)
from app.domain.enums import Permission
from app.infrastructure.database import get_db
from app.presentation.dependencies import PermissionChecker

router = APIRouter(prefix="/administration/operations", tags=["operations-readiness"])


class OperationsReadinessResponse(BaseModel):
    evaluated_at: str
    runtime_instance_id: str
    production_readiness: Dict[str, Any]
    database: Dict[str, Any]
    schedulers: List[Dict[str, Any]]
    queues: Dict[str, Any]
    integrations: List[Dict[str, Any]]
    audit_integrity: Dict[str, Any]
    security: Dict[str, Any]


@router.get("/readiness", response_model=OperationsReadinessResponse)
def get_operations_readiness(
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[AuthContext, Depends(PermissionChecker(Permission.OPERATIONS_READINESS_READ))],
) -> OperationsReadinessResponse:
    return OperationsReadinessResponse(**build_operations_readiness(db))


@router.get("/schedulers")
def get_operations_schedulers(
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[AuthContext, Depends(PermissionChecker(Permission.OPERATIONS_READINESS_READ))],
) -> Dict[str, Any]:
    return {"schedulers": get_scheduler_status(db)}


@router.get("/queues")
def get_operations_queues(
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[AuthContext, Depends(PermissionChecker(Permission.OPERATIONS_READINESS_READ))],
) -> Dict[str, Any]:
    return get_queue_status(db)


@router.get("/database")
def get_operations_database(
    _user: Annotated[AuthContext, Depends(PermissionChecker(Permission.OPERATIONS_READINESS_READ))],
) -> Dict[str, Any]:
    return get_database_status()
