"""Phase 15 — PostgreSQL production readiness, scheduler leases, operations readiness."""

import os
import tempfile
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.application.bootstrap import bootstrap_development_data
from app.application.scheduler_cycle_runner import LEASE_NOTIFICATION_DISPATCH, run_with_scheduler_lease
from app.application.scheduler_lease_service import SchedulerLeaseService
from app.core import runtime_instance
from app.core.config import settings
from app.domain.models import AdminUser, Base, RuntimeLease
from app.infrastructure.database import get_db
from app.infrastructure.database_engine import build_engine, validate_production_database_policy
from app.infrastructure.database_schema import check_schema_at_head, SchemaMismatchError
from app.main import create_app, _stop_scheduler


@pytest.fixture
def test_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    bootstrap_development_data(db)
    yield TestingSessionLocal, engine, db
    db.close()
    os.unlink(path)


@pytest.fixture
def client(test_db):
    TestingSessionLocal, _, bootstrap_session = test_db

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c, TestingSessionLocal, bootstrap_session
    app.dependency_overrides.clear()
    _stop_scheduler()


def test_database_engine_factory_sqlite():
    engine, dialect = build_engine("sqlite:///:memory:")
    assert dialect == "sqlite"
    engine.dispose()


def test_production_rejects_sqlite_database_policy(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "production_database_dialect", "postgresql")
    with pytest.raises(RuntimeError, match="PostgreSQL"):
        validate_production_database_policy("sqlite:///./data/vms.db")


def test_scheduler_lease_acquire_renew_release(test_db):
    TestingSessionLocal, _, _ = test_db
    runtime_instance._runtime_instance_id = "lease-owner-a"
    db = TestingSessionLocal()
    svc = SchedulerLeaseService(db)
    assert svc.try_acquire_or_renew(LEASE_NOTIFICATION_DISPATCH, lease_seconds=60)
    db.commit()
    assert svc.try_acquire_or_renew(LEASE_NOTIFICATION_DISPATCH, lease_seconds=60)
    db.commit()
    runtime_instance._runtime_instance_id = "lease-owner-b"
    svc_b = SchedulerLeaseService(db)
    assert not svc_b.try_acquire_or_renew(LEASE_NOTIFICATION_DISPATCH)
    db.rollback()
    lease = db.query(RuntimeLease).filter(RuntimeLease.lease_name == LEASE_NOTIFICATION_DISPATCH).first()
    lease.leased_until = datetime.now(timezone.utc) - timedelta(seconds=5)
    db.commit()
    assert svc_b.try_acquire_or_renew(LEASE_NOTIFICATION_DISPATCH)
    db.commit()
    runtime_instance._runtime_instance_id = "lease-owner-a"
    svc_a = SchedulerLeaseService(db)
    assert not svc_a.try_acquire_or_renew(LEASE_NOTIFICATION_DISPATCH)
    db.rollback()
    runtime_instance._runtime_instance_id = "lease-owner-b"
    SchedulerLeaseService(db).release_lease(LEASE_NOTIFICATION_DISPATCH)
    db.commit()
    db.close()


def test_scheduler_lease_concurrent_single_owner(test_db):
    TestingSessionLocal, _, _ = test_db
    runtime_instance._runtime_instance_id = "owner-one"
    db = TestingSessionLocal()
    assert SchedulerLeaseService(db).try_acquire_or_renew("notification-dispatch")
    db.commit()
    runtime_instance._runtime_instance_id = "owner-two"
    assert not SchedulerLeaseService(db).try_acquire_or_renew("notification-dispatch")
    db.rollback()
    db.close()


def test_run_with_scheduler_lease_skips_without_owner(test_db):
    TestingSessionLocal, _, _ = test_db
    runtime_instance._runtime_instance_id = "worker-a"
    db = TestingSessionLocal()
    assert run_with_scheduler_lease(db, LEASE_NOTIFICATION_DISPATCH, lambda _db: None)
    runtime_instance._runtime_instance_id = "worker-b"
    assert not run_with_scheduler_lease(db, LEASE_NOTIFICATION_DISPATCH, lambda _db: None)
    db.close()


def test_operations_readiness_global_admin(client):
    c, _, _ = client
    r = c.get(
        "/api/administration/operations/readiness",
        headers={"X-Dev-User-Email": "sheru.bohra@lazypay.in"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["database"]["dialect"] == "SQLite"
    assert body["database"]["environment_label"] == "DEVELOPMENT"
    assert "schedulers" in body
    assert "queues" in body
    assert "GRAPH_CLIENT_SECRET" not in r.text
    assert "password" not in r.text.lower() or "password" in "—"


def test_operations_readiness_denied_site_admin(client):
    c, _, _ = client
    r = c.get(
        "/api/administration/operations/readiness",
        headers={"X-Dev-User-Email": "siteadmin.blr@vms.local"},
    )
    assert r.status_code == 403


def test_operations_readiness_head_admin_read(client):
    c, _, _ = client
    r = c.get(
        "/api/administration/operations/readiness",
        headers={"X-Dev-User-Email": "headadmin@vms.local"},
    )
    assert r.status_code == 200


def test_health_live_ready(client):
    c, _, _ = client
    assert c.get("/api/health/live").status_code == 200
    assert c.get("/api/health/ready").status_code == 200


def test_schema_mismatch_raises_in_production(monkeypatch, test_db):
    _, engine, _ = test_db
    monkeypatch.setattr(settings, "app_env", "production")
    with pytest.raises(SchemaMismatchError):
        check_schema_at_head(engine, require_version=True)


def test_schema_behind_dev_optional(test_db):
    _, engine, _ = test_db
    info = check_schema_at_head(engine, require_version=False)
    assert info["schema_current"] is False


def test_production_config_rejects_dev_auth(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "dev_auth_enabled", False)
    monkeypatch.setattr(settings, "auth_mode", "dev")
    with pytest.raises(RuntimeError, match="AUTH_MODE"):
        settings.validate_environment()


def test_production_config_rejects_sqlite(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "dev_auth_enabled", False)
    monkeypatch.setattr(settings, "auth_mode", "vms_native")
    monkeypatch.setattr(settings, "vms_native_auth_enabled", True)
    monkeypatch.setattr(settings, "email_provider", "smtp")
    monkeypatch.setattr(settings, "public_app_base_url", "https://vms.example")
    monkeypatch.setattr(settings, "audit_integrity_key", "phase13-audit-integrity-key-for-local-vms-session-only-32c")
    monkeypatch.setattr(settings, "document_encryption_key", "phase13-document-encryption-key-for-local-vms-only-32chars")
    monkeypatch.setattr(settings, "vms_data_encryption_key", "phase13-vms-data-encryption-key-for-local-only-32c")
    monkeypatch.setattr(settings, "rate_limit_backend", "database")
    monkeypatch.setattr(settings, "file_scanner_provider", "clamav")
    monkeypatch.setattr(settings, "ai_enabled", False)
    monkeypatch.setattr(settings, "database_url", "sqlite:///./data/vms.db")
    with pytest.raises(RuntimeError, match="SQLite"):
        settings.validate_environment()
