from typing import Annotated, List

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.orm import Session

from app.application.auth_service import AuthContext
from app.application.security_readiness_service import evaluate_readiness
from app.core.config import settings
from app.core.runtime_readiness import get_audit_cache, get_schema_cache
from app.domain.models import AdminUser, Location
from app.infrastructure.database import get_db
from app.infrastructure.database_schema import check_schema_at_head
from app.presentation.dependencies import require_auth
from app.presentation.schemas import AssignedLocation, HealthResponse, MeResponse

router = APIRouter()


def _readiness_failure(code: str, message: str, checks: List[dict]) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={
            "status": "NOT_READY",
            "error": {"code": code, "message": message},
            "checks": checks,
        },
    )


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    return HealthResponse(status="ok", service="vms-api", version=settings.app_release_version)


@router.get("/health/live", response_model=HealthResponse)
def health_live() -> HealthResponse:
    return HealthResponse(status="ok", service="vms-api", version=settings.app_release_version)


@router.get("/health/ready")
def health_ready(db: Annotated[Session, Depends(get_db)]):
    checks: List[dict] = []
    try:
        db.execute(text("SELECT 1"))
        checks.append({"key": "database", "status": "CONNECTED"})
    except (OperationalError, DBAPIError):
        return _readiness_failure(
            "DATABASE_UNAVAILABLE",
            "Database connectivity check failed.",
            [{"key": "database", "status": "UNAVAILABLE"}],
        )

    schema_cache = get_schema_cache()
    if settings.is_production or settings.schema_check_on_startup:
        try:
            schema_info = check_schema_at_head(db.get_bind(), require_version=settings.is_production)
            schema_ok = schema_info.get("schema_current", False)
        except Exception as exc:
            code = getattr(exc, "code", "DATABASE_SCHEMA_OUTDATED")
            return _readiness_failure(
                code,
                str(exc),
                [{"key": "schema", "status": "OUTDATED"}],
            )
        if not schema_ok and settings.is_production:
            return _readiness_failure(
                "DATABASE_SCHEMA_OUTDATED",
                "Database schema is not at Alembic head.",
                [{"key": "schema", "status": "OUTDATED"}],
            )
        checks.append({
            "key": "schema",
            "status": "CURRENT" if schema_ok else "UNTRACKED",
            "revision": schema_info.get("current_revision"),
        })
    else:
        checks.append({
            "key": "schema",
            "status": "CURRENT" if schema_cache.get("schema_current") else "UNTRACKED",
            "revision": schema_cache.get("current_revision"),
        })

    audit = get_audit_cache()
    checks.append({
        "key": "audit_integrity",
        "status": audit.get("status", "UNCONFIGURED"),
        "verified_at": audit.get("verified_at"),
    })

    readiness = evaluate_readiness(db)
    provider_checks = readiness.get("checks", [])
    checks.extend(provider_checks)

    if settings.is_production and not readiness.get("ready"):
        return _readiness_failure(
            "RUNTIME_NOT_READY",
            "Required production providers or security configuration are not ready.",
            checks,
        )

    return {"status": "READY", "checks": checks}


@router.get("/me", response_model=MeResponse)
def get_me(
    user: Annotated[AuthContext, Depends(require_auth)],
    db: Annotated[Session, Depends(get_db)],
) -> MeResponse:
    assigned: List[AssignedLocation] = []
    if user.location_ids:
        locations = (
            db.query(Location)
            .filter(Location.id.in_(user.location_ids), Location.is_active.is_(True))
            .order_by(Location.name)
            .all()
        )
        assigned = [
            AssignedLocation(id=loc.id, name=loc.name, code=loc.code, city=loc.city)
            for loc in locations
        ]
    admin_row = db.query(AdminUser).filter(AdminUser.id == user.user_id).first()
    entra_linked = bool(
        admin_row and admin_row.entra_tenant_id and admin_row.entra_object_id
    )
    return MeResponse(
        id=user.user_id,
        email=user.email,
        display_name=user.display_name,
        role=user.role.value,
        is_owner=user.is_owner,
        is_active=admin_row.is_active if admin_row else True,
        permissions=[p.value for p in user.permissions],
        location_ids=user.location_ids,
        assigned_locations=assigned,
        auth_provider=user.auth_provider,
        force_password_change=bool(admin_row.force_password_change) if admin_row else False,
        entra_linked=entra_linked,
        last_login_at=admin_row.last_login_at.isoformat() if admin_row and admin_row.last_login_at else None,
        identity_linked_at=admin_row.identity_linked_at.isoformat() if admin_row and admin_row.identity_linked_at else None,
    )
