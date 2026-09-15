from contextlib import asynccontextmanager
import logging
import threading
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.application.audit_integrity_service import verify_chain
from app.application.bootstrap import bootstrap_application_data
from app.application.seed_cleanup import purge_development_seed_data
from app.application.data_retention_scheduler_service import run_retention_automation_cycle
from app.application.intelligence_scheduler_service import run_intelligence_cycle
from app.application.notification_dispatch_service import dispatch_pending_notifications
from app.application.notification_scheduler_service import process_upcoming_reminders
from app.application.physical_integration_scheduler import run_physical_integration_cycle
from app.application.scheduler_cycle_runner import (
    LEASE_DATA_RETENTION,
    LEASE_NOTIFICATION_DISPATCH,
    LEASE_PHYSICAL_INTEGRATIONS,
    LEASE_UPCOMING_REMINDERS,
    LEASE_VISITOR_INTELLIGENCE,
    run_with_scheduler_lease,
)
from app.application.scheduler_lease_service import SchedulerLeaseService
from app.core.config import settings
from app.core.errors import APIError, api_error_handler, database_error_handler, generic_error_handler, SecurityHeadersMiddleware
from app.core.log_sanitizer import configure_logging
from app.core.request_context import RequestIdMiddleware, RequestLoggingMiddleware
from app.core.runtime_readiness import update_audit_cache, update_schema_cache
from app.infrastructure.database import SessionLocal, dispose_engine, engine
from app.infrastructure.database_schema import check_schema_at_head, SchemaMismatchError
from app.presentation.api import router as core_router
from app.presentation.admin_api import router as admin_router
from app.presentation.admin_operations_api import router as admin_operations_router
from app.presentation.approvals_api import router as approvals_router
from app.presentation.badges_api import router as badges_router
from app.presentation.dev_notifications_api import router as dev_notifications_router
from app.presentation.host_approval_public_api import router as host_approval_public_router
from app.presentation.invitations_api import router as invitations_router
from app.presentation.visitor_media_api import router as visitor_media_router
from app.presentation.notifications_api import router as notifications_router
from app.presentation.operations_api import router as operations_router
from app.presentation.scanner_api import router as scanner_router
from app.presentation.public_api import router as public_router
from app.presentation.watchlist_api import router as watchlist_router
from app.presentation.security_review_api import router as security_review_router
from app.presentation.vendor_compliance_api import router as vendor_compliance_router
from app.presentation.emergency_roll_call_api import router as emergency_roll_call_router
from app.presentation.analytics_reports_api import router_analytics, router_reports
from app.presentation.ai_api import router as ai_router
from app.presentation.auth_api import router as auth_router
from app.presentation.admin_users_api import router as admin_users_router
from app.presentation.integrations_api import router as integrations_router
from app.presentation.privacy_security_api import router as privacy_security_router
from app.presentation.physical_integration_api import router as physical_integration_router

from typing import Optional

logger = logging.getLogger(__name__)
_scheduler_stop = threading.Event()
_scheduler_thread: Optional[threading.Thread] = None
_last_intelligence_run: float = 0.0


def _scheduler_loop() -> None:
    global _last_intelligence_run
    while not _scheduler_stop.is_set():
        try:
            db = SessionLocal()
            try:
                run_with_scheduler_lease(db, LEASE_UPCOMING_REMINDERS, process_upcoming_reminders)
                run_with_scheduler_lease(db, LEASE_NOTIFICATION_DISPATCH, dispatch_pending_notifications)
                if settings.retention_automation_enabled:
                    run_with_scheduler_lease(db, LEASE_DATA_RETENTION, run_retention_automation_cycle)
                if settings.physical_integration_scheduler_enabled:
                    run_with_scheduler_lease(db, LEASE_PHYSICAL_INTEGRATIONS, run_physical_integration_cycle)
                now = time.time()
                if now - _last_intelligence_run >= settings.intelligence_scheduler_interval_seconds:
                    if run_with_scheduler_lease(db, LEASE_VISITOR_INTELLIGENCE, run_intelligence_cycle):
                        _last_intelligence_run = now
            finally:
                db.close()
        except Exception:
            logger.exception("Background scheduler cycle failed")
        _scheduler_stop.wait(settings.scheduler_interval_seconds)


def _start_scheduler() -> None:
    global _scheduler_thread
    if not settings.background_scheduler_enabled:
        return
    if _scheduler_thread and _scheduler_thread.is_alive():
        return
    _scheduler_stop.clear()
    _scheduler_thread = threading.Thread(target=_scheduler_loop, name="vms-notification-scheduler", daemon=True)
    _scheduler_thread.start()


def _stop_scheduler() -> None:
    _scheduler_stop.set()
    if _scheduler_thread and _scheduler_thread.is_alive():
        _scheduler_thread.join(timeout=settings.app_shutdown_timeout_seconds)


def _release_scheduler_leases() -> None:
    db = SessionLocal()
    try:
        SchedulerLeaseService(db).release_all_owned()
        db.commit()
    except Exception:
        logger.exception("Failed to release scheduler leases on shutdown")
        db.rollback()
    finally:
        db.close()


def _startup_database_checks() -> None:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    require_schema = settings.is_production or settings.schema_check_on_startup
    try:
        schema_info = check_schema_at_head(engine, require_version=require_schema)
        update_schema_cache(schema_info, schema_info.get("schema_current", False))
    except SchemaMismatchError as exc:
        update_schema_cache({"current_revision": None, "head": None}, False)
        raise RuntimeError(f"{exc.code}: {exc}") from exc


def _warm_audit_cache() -> None:
    db = SessionLocal()
    try:
        update_audit_cache(verify_chain(db))
    except Exception:
        logger.exception("Initial audit integrity check failed")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings.validate_environment()
    _startup_database_checks()
    if not settings.is_production:
        from alembic import command

        from app.infrastructure.database_schema import _alembic_config

        cfg = _alembic_config()
        cfg.set_main_option("sqlalchemy.url", settings.resolved_database_url())
        command.upgrade(cfg, "head")
    db = SessionLocal()
    try:
        if not settings.is_production:
            summary = purge_development_seed_data(db)
            db.commit()
            if any(summary.values()):
                logger.info("Purged development seed data: %s", summary)
        bootstrap_application_data(db)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    _warm_audit_cache()
    _start_scheduler()
    yield
    _stop_scheduler()
    _release_scheduler_leases()
    dispose_engine()


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_exception_handler(APIError, api_error_handler)
    from sqlalchemy.exc import DBAPIError, OperationalError

    app.add_exception_handler(OperationalError, database_error_handler)
    app.add_exception_handler(DBAPIError, database_error_handler)
    app.add_exception_handler(Exception, generic_error_handler)

    app.include_router(core_router, prefix="/api")
    app.include_router(admin_router, prefix="/api")
    app.include_router(admin_operations_router, prefix="/api")
    app.include_router(approvals_router, prefix="/api")
    app.include_router(invitations_router, prefix="/api")
    app.include_router(visitor_media_router, prefix="/api")
    app.include_router(badges_router, prefix="/api")
    app.include_router(scanner_router, prefix="/api")
    app.include_router(operations_router, prefix="/api")
    app.include_router(public_router, prefix="/api")
    app.include_router(host_approval_public_router, prefix="/api")
    app.include_router(notifications_router, prefix="/api")
    app.include_router(dev_notifications_router, prefix="/api")
    app.include_router(watchlist_router, prefix="/api")
    app.include_router(security_review_router, prefix="/api")
    app.include_router(vendor_compliance_router, prefix="/api")
    app.include_router(emergency_roll_call_router, prefix="/api")
    app.include_router(router_analytics, prefix="/api")
    app.include_router(router_reports, prefix="/api")
    app.include_router(ai_router, prefix="/api")
    app.include_router(auth_router, prefix="/api")
    app.include_router(admin_users_router, prefix="/api")
    app.include_router(integrations_router, prefix="/api")
    app.include_router(privacy_security_router, prefix="/api")
    app.include_router(physical_integration_router, prefix="/api")

    return app


app = create_app()
