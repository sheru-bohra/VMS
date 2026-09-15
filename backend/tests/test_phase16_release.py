"""Phase 16 — release candidate validation regression suite."""

import os
import tempfile
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.application.audit_integrity_service import verify_chain
from app.application.bootstrap import bootstrap_development_data
from app.application.document_encryption import decrypt_bytes, encrypt_bytes
from app.application.release_readiness_service import build_release_matrix, evaluate_release_decision
from app.application.scheduler_lease_service import SchedulerLeaseService
from app.application.uat_data_service import cleanup_uat_synthetic_data, seed_uat_synthetic_visitors
from app.core import runtime_instance
from app.core.config import settings
from app.domain.models import Base, RuntimeLease, Visitor
from app.domain.release_status import IntegrationReleaseStatus, ReleaseDecision
from app.infrastructure.database import get_db
from app.main import create_app, _stop_scheduler

pytestmark = pytest.mark.release


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


STAFF_PROTECTED_PATHS = [
    "/api/reports/visits",
    "/api/analytics/dashboard",
    "/api/administration/users",
    "/api/access/credentials",
    "/api/ai/copilot/query",
    "/api/administration/operations/readiness",
]


def test_health_exposes_release_version(client):
    c, _, _ = client
    r = c.get("/api/health/live")
    assert r.status_code == 200
    body = r.json()
    assert body["service"] == "vms-api"
    assert body["version"] == settings.app_release_version


def test_unauthenticated_staff_apis_denied(test_db, monkeypatch):
    TestingSessionLocal, _, _ = test_db
    monkeypatch.setattr(settings, "auth_mode", "entra")
    monkeypatch.setattr(settings, "dev_auth_enabled", False)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        for path in STAFF_PROTECTED_PATHS:
            if path.endswith("copilot/query"):
                r = c.post(path, json={"question": "test"})
            else:
                r = c.get(path)
            assert r.status_code in (401, 403), f"{path} -> {r.status_code}"
    _stop_scheduler()


def test_site_admin_reports_denied(client):
    c, _, _ = client
    now = datetime.now(timezone.utc)
    params = {
        "from": (now - timedelta(days=7)).isoformat(),
        "to": now.isoformat(),
    }
    r = c.get(
        "/api/reports/visits",
        params=params,
        headers={"X-Dev-User-Email": "siteadmin.blr@vms.local"},
    )
    assert r.status_code == 403


def test_security_reports_denied(client):
    c, _, _ = client
    now = datetime.now(timezone.utc)
    params = {
        "from": (now - timedelta(days=7)).isoformat(),
        "to": now.isoformat(),
    }
    r = c.get(
        "/api/reports/visits",
        params=params,
        headers={"X-Dev-User-Email": "security.blr@vms.local"},
    )
    assert r.status_code == 403


def test_release_matrix_defaults_mock_tested():
    matrix = build_release_matrix(automated_tests_passed=True)
    assert matrix["core_vms"] == IntegrationReleaseStatus.UAT_APPROVED.value
    assert matrix["access_control"] in (
        IntegrationReleaseStatus.NOT_CONFIGURED.value,
        IntegrationReleaseStatus.MOCK_TESTED.value,
    )


def test_release_decision_no_go_without_live_infra(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    matrix = {
        "core_vms": IntegrationReleaseStatus.UAT_APPROVED.value,
        "postgresql": IntegrationReleaseStatus.MOCK_TESTED.value,
        "entra": IntegrationReleaseStatus.MOCK_TESTED.value,
        "graph_email": IntegrationReleaseStatus.MOCK_TESTED.value,
        "clamav": IntegrationReleaseStatus.MOCK_TESTED.value,
        "access_control": IntegrationReleaseStatus.NOT_CONFIGURED.value,
        "badge_printer": IntegrationReleaseStatus.NOT_CONFIGURED.value,
        "ai_provider": IntegrationReleaseStatus.NOT_CONFIGURED.value,
        "audit_integrity": IntegrationReleaseStatus.LIVE_VALIDATED.value,
    }
    result = evaluate_release_decision(matrix=matrix, automated_tests_passed=True, audit_valid=True)
    assert result["decision"] == ReleaseDecision.NO_GO.value
    assert result["blockers"]


def test_release_conditional_go_optional_integrations_disabled(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "access_control_enabled", False)
    monkeypatch.setattr(settings, "badge_printer_enabled", False)
    matrix = build_release_matrix(automated_tests_passed=True)
    result = evaluate_release_decision(matrix=matrix, automated_tests_passed=True, audit_valid=True)
    assert result["decision"] in (ReleaseDecision.GO.value, ReleaseDecision.CONDITIONAL_GO.value)


def test_uat_synthetic_seed_and_cleanup(test_db):
    TestingSessionLocal, _, session = test_db
    created = seed_uat_synthetic_visitors(session)
    assert created >= 1
    count = session.query(Visitor).filter(Visitor.email.endswith("@example.invalid")).count()
    assert count >= 1
    result = cleanup_uat_synthetic_data(session)
    assert result["visitors_removed"] >= 1
    assert session.query(Visitor).filter(Visitor.email.endswith("@example.invalid")).count() == 0


def test_document_encryption_restart_roundtrip(monkeypatch):
    key = "abcdefghijklmnopabcdefghijklmnop1234"
    monkeypatch.setattr(settings, "document_encryption_key", key)
    plaintext = b"UAT compliance document bytes"
    encrypted, ver = encrypt_bytes(plaintext)
    assert decrypt_bytes(encrypted, ver) == plaintext


def test_document_encryption_wrong_key_fails(monkeypatch):
    monkeypatch.setattr(settings, "document_encryption_key", "abcdefghijklmnopabcdefghijklmnop1234")
    encrypted, ver = encrypt_bytes(b"payload-bytes")
    monkeypatch.setattr(settings, "document_encryption_key", "bcdefghijklmnopabcdefghijklmnop1235")
    with pytest.raises(Exception):
        decrypt_bytes(encrypted, ver)


def test_audit_integrity_valid_after_operations(test_db):
    TestingSessionLocal, _, session = test_db
    from app.application.audit_service import AuditService

    AuditService(session).record(
        action="RELEASE_TEST",
        entity_type="TEST",
        entity_id="1",
        metadata={"phase": 16},
    )
    session.commit()
    result = verify_chain(session)
    assert result["status"] == "VALID"


def test_scheduler_multi_instance_single_owner(test_db):
    TestingSessionLocal, _, _ = test_db
    runtime_instance._runtime_instance_id = "rc-a"
    db = TestingSessionLocal()
    assert SchedulerLeaseService(db).try_acquire_or_renew("data-retention")
    db.commit()
    runtime_instance._runtime_instance_id = "rc-b"
    assert not SchedulerLeaseService(db).try_acquire_or_renew("data-retention")
    db.rollback()
    db.close()


def test_scheduler_lease_failover(test_db):
    TestingSessionLocal, _, _ = test_db
    runtime_instance._runtime_instance_id = "rc-owner"
    db = TestingSessionLocal()
    SchedulerLeaseService(db).try_acquire_or_renew("physical-integrations", lease_seconds=30)
    db.commit()
    lease = db.query(RuntimeLease).filter(RuntimeLease.lease_name == "physical-integrations").first()
    lease.leased_until = datetime.now(timezone.utc) - timedelta(seconds=5)
    db.commit()
    runtime_instance._runtime_instance_id = "rc-failover"
    assert SchedulerLeaseService(db).try_acquire_or_renew("physical-integrations")
    db.commit()
    db.close()


def test_csp_security_headers_release(client):
    c, _, _ = client
    r = c.get("/api/health/live")
    csp = r.headers.get("Content-Security-Policy", "")
    assert "default-src" in csp
    assert "unsafe-eval" not in csp


def test_log_sanitizer_redacts_database_url():
    from app.core.log_sanitizer import _sanitize

    msg = _sanitize("connect failed postgresql://user:secret@db.example.com/vms")
    assert "secret" not in msg
    assert "postgresql://[REDACTED]" in msg or "REDACTED" in msg


def test_health_ready_without_auth(client):
    c, _, _ = client
    r = c.get("/api/health/ready")
    assert r.status_code == 200


def test_operations_readiness_no_secrets(client):
    c, _, _ = client
    r = c.get(
        "/api/administration/operations/readiness",
        headers={"X-Dev-User-Email": "sheru.bohra@lazypay.in"},
    )
    assert r.status_code == 200
    assert "GRAPH_CLIENT_SECRET" not in r.text
    assert "password" not in r.text.lower() or "—" in r.text
