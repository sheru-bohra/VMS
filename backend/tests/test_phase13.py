"""Phase 13 — security, privacy, retention hardening."""

import io
import os
import tempfile
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.application.audit_integrity_service import backfill_unsealed_events, verify_chain
from app.application.bootstrap import bootstrap_development_data
from app.application.compliance_document_service import upload_document
from app.application.data_retention_service import create_policy, execute_policy, preview_policy
from app.application.auth_service import build_auth_context
from app.application.document_encryption import encrypt_bytes, decrypt_bytes
from app.application.file_security_scanner import ScanResult
from app.application.rate_limit_store import DatabaseRateLimitStore, InMemoryRateLimitStore
from app.core.config import settings
from app.core.log_sanitizer import SensitiveLoggingFilter
from app.domain.enums import VisitStatus
from app.domain.models import AdminUser, AIInteraction, AuditEvent, DataRetentionPolicy, DataRetentionRunDedupe, Location, Notification, Visit, Visitor
from app.infrastructure.database import Base, get_db
from app.main import create_app


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


def _owner_ctx(session):
    owner = session.query(AdminUser).filter(AdminUser.email == "sheru.bohra@lazypay.in").first()
    return build_auth_context(owner)


def test_audit_seal_and_verify(test_db):
    TestingSessionLocal, _, session = test_db
    db = TestingSessionLocal()
    from app.application.audit_service import AuditService
    event = AuditService(db).record(action="TEST_AUDIT", entity_type="test", entity_id="1")
    db.commit()
    assert event.integrity_sequence is not None
    assert event.integrity_hash
    # Legacy bootstrap events may remain unsealed until backfill
    legacy = AuditEvent(
        action="LEGACY_UNSEALED",
        entity_type="test",
        entity_id="legacy-1",
    )
    db.add(legacy)
    db.flush()
    sealed = backfill_unsealed_events(db)
    db.commit()
    assert sealed >= 1
    db.refresh(legacy)
    assert legacy.integrity_sequence is not None
    result = verify_chain(db)
    assert result["status"] in ("VALID", "UNSEALED_LEGACY_EVENTS")


def test_audit_tamper_detected(test_db):
    TestingSessionLocal, _, session = test_db
    db = TestingSessionLocal()
    from app.application.audit_service import AuditService
    AuditService(db).record(action="TAMPER_TEST", entity_type="test", entity_id="2")
    db.commit()
    backfill_unsealed_events(db)
    db.commit()
    event = db.query(AuditEvent).filter(AuditEvent.action == "TAMPER_TEST").first()
    event.action = "MODIFIED"
    db.commit()
    result = verify_chain(db)
    assert result["status"] == "BROKEN"


def test_production_rejects_memory_rate_limit(monkeypatch):
    from cryptography.fernet import Fernet
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "auth_mode", "vms_native")
    monkeypatch.setattr(settings, "vms_native_auth_enabled", True)
    monkeypatch.setattr(settings, "dev_auth_enabled", False)
    monkeypatch.setattr(settings, "email_provider", "smtp")
    monkeypatch.setattr(settings, "ai_enabled", False)
    monkeypatch.setattr(settings, "public_app_base_url", "https://vms.example.com")
    monkeypatch.setattr(settings, "rate_limit_backend", "memory")
    monkeypatch.setattr(settings, "file_scanner_provider", "clamav")
    monkeypatch.setattr(settings, "audit_integrity_key", "phase13-audit-integrity-key-for-production-validation-32")
    monkeypatch.setattr(settings, "vms_data_encryption_key", Fernet.generate_key().decode())
    monkeypatch.setattr(settings, "document_encryption_key", "phase13-document-encryption-key-for-production-32")
    with pytest.raises(RuntimeError, match="RATE_LIMIT_BACKEND"):
        settings.validate_environment()


def test_database_rate_limit_store_shared(test_db):
    TestingSessionLocal, _, _ = test_db
    store = DatabaseRateLimitStore(TestingSessionLocal)
    assert store.check_and_increment("bucket:test", 2, 60)
    assert store.check_and_increment("bucket:test", 2, 60)
    assert not store.check_and_increment("bucket:test", 2, 60)


def test_visitor_pii_retention_anonymizes(test_db):
    TestingSessionLocal, _, session = test_db
    owner = _owner_ctx(session)
    db = TestingSessionLocal()
    policy = db.query(DataRetentionPolicy).filter(DataRetentionPolicy.data_category == "VISITOR_PII").first()
    assert policy is not None
    old = datetime.now(timezone.utc) - timedelta(days=400)
    visitor = Visitor(full_name="Old Guest", email="oldguest@test.com", phone="+911111111111", privacy_state="ACTIVE")
    db.add(visitor)
    db.flush()
    loc = session.query(Location).filter(Location.code == "BLR").first()
    visit = Visit(
        visitor_id=visitor.id,
        location_id=loc.id,
        status=VisitStatus.CHECKED_OUT.value,
    )
    db.add(visit)
    db.flush()
    visit.updated_at = old
    db.commit()
    result = execute_policy(db, owner, policy.id)
    db.commit()
    session.expire_all()
    refreshed = session.query(Visitor).filter(Visitor.id == visitor.id).first()
    assert result["processed_count"] >= 1
    assert refreshed.privacy_state == "ANONYMIZED"
    assert refreshed.email is None


def test_active_onsite_visitor_skipped(test_db):
    TestingSessionLocal, _, session = test_db
    owner = _owner_ctx(session)
    db = TestingSessionLocal()
    policy = db.query(DataRetentionPolicy).filter(DataRetentionPolicy.data_category == "VISITOR_PII").first()
    visitor = Visitor(full_name="Onsite Guest", email="onsite@test.com", privacy_state="ACTIVE")
    db.add(visitor)
    db.flush()
    loc = session.query(Location).filter(Location.code == "BLR").first()
    visit = Visit(visitor_id=visitor.id, location_id=loc.id, status=VisitStatus.ONSITE.value)
    db.add(visit)
    db.commit()
    preview = preview_policy(db, owner, policy.id)
    db.commit()
    assert preview["skipped_count"] >= 1


def test_notification_content_purged(test_db):
    TestingSessionLocal, _, session = test_db
    owner = _owner_ctx(session)
    db = TestingSessionLocal()
    policy = db.query(DataRetentionPolicy).filter(DataRetentionPolicy.data_category == "NOTIFICATION_CONTENT").first()
    old = datetime.now(timezone.utc) - timedelta(days=120)
    notif = Notification(
        notification_type="TEST",
        channel="EMAIL",
        recipient="host@example.com",
        status="SENT",
        template_key="test",
        payload_json='{"secret":"data"}',
        dedupe_key=f"test-purge-{old.isoformat()}",
        subject="Secret subject",
        body_preview="Secret body",
        created_at=old,
    )
    db.add(notif)
    db.commit()
    execute_policy(db, owner, policy.id)
    db.commit()
    session.expire_all()
    row = session.query(Notification).filter(Notification.id == notif.id).first()
    assert row.body_preview == "[Removed by retention policy]"
    assert row.recipient == "purged@invalid.local"


def test_document_encryption_roundtrip():
    data = b"PDF test content"
    blob, ver = encrypt_bytes(data)
    assert decrypt_bytes(blob, ver) == data


def test_infected_upload_rejected(test_db, monkeypatch):
    TestingSessionLocal, _, session = test_db
    owner = _owner_ctx(session)
    db = TestingSessionLocal()
    from app.application.vendor_company_service import create_vendor_company
    from app.domain.models import ComplianceRequirement
    requirement = session.query(ComplianceRequirement).filter(
        ComplianceRequirement.document_owner_type == "COMPANY"
    ).first()
    if not requirement:
        pytest.skip("compliance requirement fixtures missing")
    blr = session.query(Location).filter(Location.code == "BLR").first()
    vendor = create_vendor_company(db, owner, name="Phase13 Vendor Co", location_ids=[blr.id], code="P13V")
    db.commit()
    with patch("app.application.document_storage.get_file_security_scanner") as mock_scanner:
        scanner = mock_scanner.return_value
        scanner.scan_file.return_value = ScanResult.INFECTED
        from app.application.compliance_document_service import ComplianceDocumentError
        with pytest.raises(ComplianceDocumentError) as exc:
            upload_document(
                db,
                owner,
                requirement.id,
                io.BytesIO(b"bad"),
                "bad.pdf",
                "application/pdf",
                3,
                vendor_company_id=vendor["id"],
            )
        assert exc.value.code == "FILE_SECURITY_REJECTED"


def test_location_retention_override(test_db):
    TestingSessionLocal, _, session = test_db
    owner = _owner_ctx(session)
    db = TestingSessionLocal()
    blr = session.query(Location).filter(Location.code == "BLR").first()
    mum = session.query(Location).filter(Location.code == "MUM").first()
    create_policy(db, owner, "VISITOR_PII", "LOCATION", 180, "ANONYMIZE", blr.id)
    db.commit()
    old = datetime.now(timezone.utc) - timedelta(days=200)
    blr_visitor = Visitor(full_name="Old BLR", phone="+911111111111", email="oldblr@example.com", privacy_state="ACTIVE")
    mum_visitor = Visitor(full_name="Old MUM", phone="+922222222222", email="oldmum@example.com", privacy_state="ACTIVE")
    db.add_all([blr_visitor, mum_visitor])
    db.flush()
    db.add(
        Visit(
            visitor_id=blr_visitor.id,
            location_id=blr.id,
            status=VisitStatus.CHECKED_OUT.value,
            purpose="old",
            updated_at=old,
        )
    )
    db.add(
        Visit(
            visitor_id=mum_visitor.id,
            location_id=mum.id,
            status=VisitStatus.CHECKED_OUT.value,
            purpose="old",
            updated_at=old,
        )
    )
    db.commit()
    blr_policy = (
        db.query(DataRetentionPolicy)
        .filter(DataRetentionPolicy.scope_type == "LOCATION", DataRetentionPolicy.location_id == blr.id)
        .first()
    )
    preview_blr = preview_policy(db, owner, blr_policy.id)
    global_policy = db.query(DataRetentionPolicy).filter(
        DataRetentionPolicy.data_category == "VISITOR_PII", DataRetentionPolicy.scope_type == "GLOBAL"
    ).first()
    preview_global = preview_policy(db, owner, global_policy.id)
    db.commit()
    assert blr_visitor.id in preview_blr["eligible_ids_sample"] or preview_blr["eligible_count"] >= 1
    assert mum_visitor.id not in preview_global.get("eligible_ids_sample", [])
    assert preview_global["eligible_count"] == 0 or mum_visitor.id not in preview_global["eligible_ids_sample"]


def test_cors_allows_configured_origin(client):
    c, _, _ = client
    origin = settings.cors_origin_list[0]
    r = c.get("/api/health", headers={"Origin": origin})
    assert r.headers.get("access-control-allow-origin") == origin


def test_cors_rejects_unknown_origin(client):
    c, _, _ = client
    r = c.get("/api/health", headers={"Origin": "https://evil.example"})
    assert r.headers.get("access-control-allow-origin") != "https://evil.example"


def test_idor_cross_location_visit_denied(client, test_db):
    c, _, _ = client
    _, _, session = test_db
    mum = session.query(Location).filter(Location.code == "MUM").first()
    visitor = Visitor(full_name="Mum IDOR", privacy_state="ACTIVE")
    session.add(visitor)
    session.flush()
    visit = Visit(visitor_id=visitor.id, location_id=mum.id, status=VisitStatus.APPROVED.value)
    session.add(visit)
    session.commit()
    r = c.get(f"/api/visits/{visit.id}", headers={"X-Dev-User-Email": "security.blr@vms.local"})
    assert r.status_code in (403, 404)


def test_idor_cross_location_emergency_denied(client, test_db):
    c, _, _ = client
    _, _, session = test_db
    from app.domain.models import EmergencyEvent
    mum = session.query(Location).filter(Location.code == "MUM").first()
    owner = session.query(AdminUser).filter(AdminUser.email == "sheru.bohra@lazypay.in").first()
    event = EmergencyEvent(
        location_id=mum.id,
        status="CLOSED",
        reason="IDOR_TEST",
        started_by_user_id=owner.id,
        closed_at=datetime.now(timezone.utc),
    )
    session.add(event)
    session.commit()
    r = c.get(f"/api/emergencies/{event.id}", headers={"X-Dev-User-Email": "security.blr@vms.local"})
    assert r.status_code in (403, 404)


def test_mass_assignment_role_escalation_denied(client):
    c, _, _ = client
    r = c.patch(
        "/api/administration/users/2",
        headers={"X-Dev-User-Email": "siteadmin.blr@vms.local"},
        json={"role": "GLOBAL_ADMIN", "is_owner": True},
    )
    assert r.status_code in (403, 404)


def test_retention_scheduler_dedupe(test_db, monkeypatch):
    monkeypatch.setattr(settings, "retention_automation_enabled", True)
    TestingSessionLocal, _, session = test_db
    db = TestingSessionLocal()
    policy = db.query(DataRetentionPolicy).filter(DataRetentionPolicy.data_category == "NOTIFICATION_CONTENT").first()
    old = datetime.now(timezone.utc) - timedelta(days=120)
    db.add(
        Notification(
            notification_type="SCHED_TEST",
            channel="EMAIL",
            recipient="sched@example.com",
            status="SENT",
            template_key="sched",
            payload_json='{"x":1}',
            dedupe_key=f"sched-dedupe-{old.isoformat()}",
            subject="sched",
            body_preview="sched body",
            created_at=old,
        )
    )
    db.commit()
    from app.application.data_retention_scheduler_service import run_retention_automation_cycle
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(settings, "retention_automation_enabled", True)
    run_retention_automation_cycle(db)
    db.commit()
    today = datetime.now(timezone.utc).date().isoformat()
    dedupe_count = (
        db.query(DataRetentionRunDedupe)
        .filter(DataRetentionRunDedupe.policy_id == policy.id, DataRetentionRunDedupe.scheduled_date == today)
        .count()
    )
    assert dedupe_count >= 1
    run_retention_automation_cycle(db)
    db.commit()
    dedupe_count2 = (
        db.query(DataRetentionRunDedupe)
        .filter(DataRetentionRunDedupe.policy_id == policy.id, DataRetentionRunDedupe.scheduled_date == today)
        .count()
    )
    assert dedupe_count2 == dedupe_count


def test_production_config_rejects_dev_providers(monkeypatch):
    from cryptography.fernet import Fernet
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "auth_mode", "dev")
    monkeypatch.setattr(settings, "dev_auth_enabled", False)
    with pytest.raises(RuntimeError, match="AUTH_MODE"):
        settings.validate_environment()
    monkeypatch.setattr(settings, "auth_mode", "vms_native")
    monkeypatch.setattr(settings, "vms_native_auth_enabled", True)
    monkeypatch.setattr(settings, "email_provider", "dev_outbox")
    with pytest.raises(RuntimeError, match="dev_outbox"):
        settings.validate_environment()
    monkeypatch.setattr(settings, "email_provider", "ms_graph")
    monkeypatch.setattr(settings, "ai_enabled", False)
    with pytest.raises(RuntimeError, match="ms_graph"):
        settings.validate_environment()
    monkeypatch.setattr(settings, "email_provider", "smtp")
    monkeypatch.setattr(settings, "ai_enabled", False)
    monkeypatch.setattr(settings, "public_app_base_url", "http://insecure.example")
    with pytest.raises(RuntimeError, match="HTTPS"):
        settings.validate_environment()
    monkeypatch.setattr(settings, "public_app_base_url", "https://vms.example")
    monkeypatch.setattr(settings, "audit_integrity_key", "weak")
    with pytest.raises(RuntimeError, match="AUDIT_INTEGRITY_KEY"):
        settings.validate_environment()


def test_log_sanitizer_redacts_bearer():
    filt = SensitiveLoggingFilter()
    record = __import__("logging").LogRecord("t", 0, "", 0, "Bearer secret-token-value", None, None)
    filt.filter(record)
    assert "secret-token" not in record.getMessage()


def test_security_headers_on_health(client):
    c, _, _ = client
    r = c.get("/api/health")
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert "Content-Security-Policy" in r.headers


def test_privacy_security_api_denied_site_admin(client):
    c, _, _ = client
    r = c.get("/api/administration/privacy-security/retention/policies", headers={"X-Dev-User-Email": "siteadmin.blr@vms.local"})
    assert r.status_code == 403


def test_health_live_ready(client):
    c, _, _ = client
    assert c.get("/api/health/live").status_code == 200
    assert c.get("/api/health/ready").status_code == 200


def test_retention_idempotent(test_db):
    TestingSessionLocal, _, session = test_db
    owner = _owner_ctx(session)
    db = TestingSessionLocal()
    policy = db.query(DataRetentionPolicy).filter(DataRetentionPolicy.data_category == "AI_INTERACTION").first()
    old = datetime.now(timezone.utc) - timedelta(days=60)
    row = AIInteraction(user_id=owner.user_id, intent="TEST", provider="dev_mock", status="COMPLETED", question_redacted="q", response_summary="r", created_at=old)
    db.add(row)
    db.commit()
    r1 = execute_policy(db, owner, policy.id)
    db.commit()
    r2 = execute_policy(db, owner, policy.id)
    db.commit()
    assert r1["processed_count"] >= 1
    assert r2["processed_count"] == 0
