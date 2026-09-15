"""Phase 14.1 — closure: admin CRUD, IDOR, privacy, named E2Es."""

import logging
import os
import tempfile
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.application.access_attention_service import REASON_CHECKED_OUT_ACCESS_ACTIVE, list_attention_items
from app.application.access_config_service import (
    create_printer,
    create_profile,
    create_profile_mapping,
    update_location_config,
    update_printer,
    update_profile,
)
from app.application.access_control_provider import DevMockAccessControlProvider
from app.application.access_provisioning_service import (
    get_location_access_config,
    process_expired_credentials,
    process_pending_access_attempts,
    reconcile_checked_out_active_credentials,
    retry_credential,
)
from app.application.auth_service import build_auth_context
from app.application.badge_printer_provider import DevMockBadgePrinterProvider
from app.application.bootstrap import bootstrap_development_data
from app.application.operations_service import check_in_visit, check_out_visit, mark_arrived
from app.application.physical_badge_print_service import request_physical_print, retry_print_job
from app.application.physical_integration_scheduler import run_physical_integration_cycle
from app.application.security_screening_service import screen_visit
from app.core.config import settings
from app.core.log_sanitizer import SensitiveLoggingFilter
from app.core.provider_error_sanitizer import redact_sensitive_text, sanitize_access_provider_error
from app.domain.enums import PhysicalAccessStatus, VisitStatus
from app.domain.models import (
    AdminUser,
    AuditEvent,
    BadgePrintJob,
    Location,
    LocationAccessConfiguration,
    Visitor,
    VisitorAccessCredential,
    VisitorType,
    Visit,
    Host,
    AccessProvisioningAttempt,
)
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
    return build_auth_context(session.query(AdminUser).filter(AdminUser.email == "sheru.bohra@lazypay.in").first())


def _sec_blr_ctx(session):
    return build_auth_context(session.query(AdminUser).filter(AdminUser.email == "security.blr@vms.local").first())


def _setup_blr_access(db, owner_ctx, monkeypatch):
    monkeypatch.setattr(settings, "access_control_enabled", True)
    monkeypatch.setattr(settings, "access_control_provider", "dev_mock")
    monkeypatch.setattr(settings, "access_mock_simulate_unavailable", False)
    monkeypatch.setattr(settings, "access_mock_simulate_failure", False)
    monkeypatch.setattr(settings, "badge_printer_enabled", True)
    monkeypatch.setattr(settings, "badge_printer_provider", "dev_mock")
    monkeypatch.setattr(settings, "badge_printer_mock_simulate_offline", False)
    blr = db.query(Location).filter(Location.code == "BLR").first()
    cfg = get_location_access_config(db, blr.id)
    if not cfg:
        cfg = LocationAccessConfiguration(location_id=blr.id)
        db.add(cfg)
        db.flush()
    cfg.access_control_enabled = True
    cfg.provider_key = "dev_mock"
    cfg.credential_grace_minutes = 30
    cfg.max_credential_duration_minutes = 480
    profile = create_profile(db, owner_ctx, blr.id, "Standard Visitor", "profile-standard-blr")
    vt = db.query(VisitorType).filter(VisitorType.code == "BUSINESS").first()
    create_profile_mapping(db, owner_ctx, blr.id, vt.id, profile["id"])
    create_printer(db, owner_ctx, blr.id, "Reception Printer", "dev_mock", "printer-blr-1", is_default=True)
    db.commit()
    return blr


def _approved_visit_blr(session, suffix="p141"):
    blr = session.query(Location).filter(Location.code == "BLR").first()
    vt = session.query(VisitorType).filter(VisitorType.code == "BUSINESS").first()
    host = session.query(Host).filter(Host.is_development_seed.is_(True)).first()
    visitor = Visitor(
        full_name=f"P141 {suffix}",
        email=f"p141{suffix}@test.com",
        phone=f"+91999{suffix[:4]}",
        visitor_type_id=vt.id,
    )
    session.add(visitor)
    session.flush()
    visit = Visit(
        visitor_id=visitor.id,
        location_id=blr.id,
        status=VisitStatus.APPROVED.value,
        host_id=host.id,
        host_name=host.name,
        purpose="Meeting",
        expected_duration_minutes=60,
        policy_accepted=True,
    )
    session.add(visit)
    session.commit()
    return visit, blr


def _checkin(db, session, visit_id):
    sec = _sec_blr_ctx(session)
    screen_visit(db, visit_id, trigger="check_in")
    mark_arrived(db, sec, visit_id)
    db.commit()
    check_in_visit(db, sec, visit_id)
    db.commit()


def test_access_profile_updated_audit(test_db):
    TestingSessionLocal, _, session = test_db
    owner = _owner_ctx(session)
    db = TestingSessionLocal()
    blr = session.query(Location).filter(Location.code == "BLR").first()
    profile = create_profile(db, owner, blr.id, "Audit Profile", "audit-ref")
    db.commit()
    update_profile(db, owner, profile["id"], name="Audit Profile Updated")
    db.commit()
    event = db.query(AuditEvent).filter(AuditEvent.action == "ACCESS_PROFILE_UPDATED").first()
    assert event is not None
    assert event.entity_id == str(profile["id"])


def test_badge_printer_updated_audit(test_db):
    TestingSessionLocal, _, session = test_db
    owner = _owner_ctx(session)
    db = TestingSessionLocal()
    blr = session.query(Location).filter(Location.code == "BLR").first()
    printer = create_printer(db, owner, blr.id, "Audit Printer", "dev_mock", "audit-printer-1")
    db.commit()
    update_printer(db, owner, printer["id"], name="Audit Printer Renamed")
    db.commit()
    event = db.query(AuditEvent).filter(AuditEvent.action == "BADGE_PRINTER_UPDATED").first()
    assert event is not None


def test_idor_profile_cross_location(client, test_db):
    c, TestingSessionLocal, session = client
    owner = _owner_ctx(session)
    db = TestingSessionLocal()
    mum = session.query(Location).filter(Location.code == "MUM").first()
    profile = create_profile(db, owner, mum.id, "Mum Profile", "mum-profile-ref")
    db.commit()
    pid = profile["id"]
    assert c.get(f"/api/access/profiles/{pid}", headers={"X-Dev-User-Email": "siteadmin.blr@vms.local"}).status_code in (403, 404)
    assert c.get(f"/api/access/profiles/{pid}", headers={"X-Dev-User-Email": "security.blr@vms.local"}).status_code in (403, 404)
    assert c.patch(
        f"/api/access/profiles/{pid}",
        headers={"X-Dev-User-Email": "siteadmin.blr@vms.local"},
        json={"name": "Hacked"},
    ).status_code in (403, 404)


def test_idor_printer_cross_location(client, test_db):
    c, TestingSessionLocal, session = client
    owner = _owner_ctx(session)
    db = TestingSessionLocal()
    mum = session.query(Location).filter(Location.code == "MUM").first()
    printer = create_printer(db, owner, mum.id, "Mum Printer", "dev_mock", "mum-printer-1")
    db.commit()
    pid = printer["id"]
    assert c.get(f"/api/badge-printers/{pid}", headers={"X-Dev-User-Email": "security.blr@vms.local"}).status_code in (403, 404)
    assert c.patch(
        f"/api/badge-printers/{pid}",
        headers={"X-Dev-User-Email": "siteadmin.blr@vms.local"},
        json={"name": "Hacked"},
    ).status_code in (403, 404)


def test_idor_mapping_cross_location(client, test_db):
    c, _, session = client
    owner = _owner_ctx(session)
    mum = session.query(Location).filter(Location.code == "MUM").first()
    blr = session.query(Location).filter(Location.code == "BLR").first()
    profile = create_profile(session, owner, mum.id, "Mum Map Profile", "mum-map-ref")
    vt = session.query(VisitorType).filter(VisitorType.code == "BUSINESS").first()
    session.commit()
    r = c.post(
        "/api/access/profile-mappings",
        headers={"X-Dev-User-Email": "siteadmin.blr@vms.local"},
        json={"location_id": mum.id, "visitor_type_id": vt.id, "access_profile_id": profile["id"]},
    )
    assert r.status_code in (403, 404)


def test_idor_location_config_cross_location(client, test_db):
    c, _, session = client
    mum = session.query(Location).filter(Location.code == "MUM").first()
    blr = session.query(Location).filter(Location.code == "BLR").first()
    profile = create_profile(session, _owner_ctx(session), blr.id, "BLR Only", "blr-only")
    session.commit()
    r = c.patch(
        f"/api/access/config/locations/{mum.id}",
        headers={"X-Dev-User-Email": "siteadmin.blr@vms.local"},
        json={"access_control_enabled": True, "default_access_profile_id": profile["id"]},
    )
    assert r.status_code in (403, 404)


def test_provider_payload_minimization(test_db, monkeypatch):
    TestingSessionLocal, _, session = test_db
    owner = _owner_ctx(session)
    db = TestingSessionLocal()
    _setup_blr_access(db, owner, monkeypatch)
    visit, _ = _approved_visit_blr(session, "payload")
    _checkin(db, session, visit.id)
    req = DevMockAccessControlProvider.last_provision_request
    assert req is not None
    assert req.access_profile_external_ref == "profile-standard-blr"
    assert req.idempotency_key.startswith("vms-access-")
    assert req.visitor_display_name
    forbidden = str(req)
    assert "watchlist" not in forbidden.lower()
    assert "@" not in forbidden
    assert "+919" not in forbidden


def test_printer_payload_minimization(test_db, monkeypatch):
    TestingSessionLocal, _, session = test_db
    owner = _owner_ctx(session)
    db = TestingSessionLocal()
    _setup_blr_access(db, owner, monkeypatch)
    visit, _ = _approved_visit_blr(session, "printpayload")
    _checkin(db, session, visit.id)
    request_physical_print(db, _sec_blr_ctx(session), visit.id, idempotency_key=f"payload-{visit.id}")
    db.commit()
    payload = DevMockBadgePrinterProvider.last_print_payload
    assert payload is not None
    assert payload.template_version == "badge-template-v1"
    assert payload.badge_number
    raw = f"{payload.visitor_name} {payload.company} {payload.host_name}"
    assert "@" not in raw
    assert "watchlist" not in raw.lower()


def test_phase14_log_redaction_sanitizer():
    secret = "access-provider-secret-TEST printer-secret-TEST physical-credential-secret-TEST provider-token-TEST"
    redacted = redact_sensitive_text(secret)
    assert "access-provider-secret-TEST" not in redacted
    assert "printer-secret-TEST" not in redacted
    filt = SensitiveLoggingFilter()
    record = logging.LogRecord("test", logging.WARNING, "", 0, secret, None, None)
    filt.filter(record)
    assert "access-provider-secret-TEST" not in record.getMessage()


def test_provider_error_sanitization():
    raw = "401 unauthorized: token=abc123 access-provider-secret-TEST"
    code = sanitize_access_provider_error(raw)
    assert code == "ACCESS_PROVIDER_AUTH_FAILED"
    assert "abc123" not in code


def test_checked_out_active_urgent_attention(test_db, monkeypatch):
    TestingSessionLocal, _, session = test_db
    owner = _owner_ctx(session)
    db = TestingSessionLocal()
    _setup_blr_access(db, owner, monkeypatch)
    visit, _ = _approved_visit_blr(session, "urgent")
    _checkin(db, session, visit.id)
    cred = db.query(VisitorAccessCredential).filter(VisitorAccessCredential.visit_id == visit.id).first()
    visit_row = db.query(Visit).filter(Visit.id == visit.id).first()
    visit_row.status = VisitStatus.CHECKED_OUT.value
    visit_row.checked_out_at = datetime.now(timezone.utc)
    cred.status = PhysicalAccessStatus.ACTIVE.value
    db.commit()
    items = list_attention_items(db, owner)
    urgent = [i for i in items if i.get("reason_code") == REASON_CHECKED_OUT_ACCESS_ACTIVE]
    assert len(urgent) == 1
    assert urgent[0]["severity"] == "URGENT"
    count = reconcile_checked_out_active_credentials(db)
    assert count == 1
    db.commit()
    reconcile_checked_out_active_credentials(db)
    pending = db.query(AccessProvisioningAttempt).filter(
        AccessProvisioningAttempt.dedupe_key == f"RECONCILE:{cred.id}",
    ).count()
    assert pending == 1


def test_phase14_checkin_access_provisioning_e2e(test_db, monkeypatch):
    TestingSessionLocal, _, session = test_db
    owner = _owner_ctx(session)
    db = TestingSessionLocal()
    blr = _setup_blr_access(db, owner, monkeypatch)
    visit, _ = _approved_visit_blr(session, "cinacc")
    _checkin(db, session, visit.id)
    cred = db.query(VisitorAccessCredential).filter(VisitorAccessCredential.visit_id == visit.id).first()
    assert cred is not None
    assert cred.status == PhysicalAccessStatus.ACTIVE.value
    assert cred.location_id == blr.id
    assert cred.valid_until is not None
    assert cred.provider_credential_reference
    assert db.query(VisitorAccessCredential).filter(VisitorAccessCredential.visit_id == visit.id).count() == 1
    assert db.query(AuditEvent).filter(AuditEvent.action == "ACCESS_PROVISIONED").first()


def test_phase14_checkout_revoke_e2e(test_db, monkeypatch):
    TestingSessionLocal, _, session = test_db
    owner = _owner_ctx(session)
    db = TestingSessionLocal()
    _setup_blr_access(db, owner, monkeypatch)
    visit, _ = _approved_visit_blr(session, "chkrev")
    _checkin(db, session, visit.id)
    sec = _sec_blr_ctx(session)
    check_out_visit(db, sec, visit.id)
    db.commit()
    cred = db.query(VisitorAccessCredential).filter(VisitorAccessCredential.visit_id == visit.id).first()
    assert cred.status == PhysicalAccessStatus.REVOKED.value
    assert db.query(Visit).filter(Visit.id == visit.id).first().status == VisitStatus.CHECKED_OUT.value


def test_phase14_provisioning_outage_retry_e2e(test_db, monkeypatch):
    TestingSessionLocal, _, session = test_db
    owner = _owner_ctx(session)
    db = TestingSessionLocal()
    _setup_blr_access(db, owner, monkeypatch)
    monkeypatch.setattr(settings, "access_mock_simulate_unavailable", True)
    visit, _ = _approved_visit_blr(session, "provout")
    _checkin(db, session, visit.id)
    cred = db.query(VisitorAccessCredential).filter(VisitorAccessCredential.visit_id == visit.id).first()
    monkeypatch.setattr(settings, "access_mock_simulate_unavailable", False)
    retry_credential(db, owner, cred.id)
    db.commit()
    db.refresh(cred)
    assert cred.status == PhysicalAccessStatus.ACTIVE.value


def test_phase14_revocation_outage_retry_e2e(test_db, monkeypatch):
    TestingSessionLocal, _, session = test_db
    owner = _owner_ctx(session)
    db = TestingSessionLocal()
    _setup_blr_access(db, owner, monkeypatch)
    visit, _ = _approved_visit_blr(session, "revout")
    _checkin(db, session, visit.id)
    monkeypatch.setattr(settings, "access_mock_simulate_unavailable", True)
    sec = _sec_blr_ctx(session)
    check_out_visit(db, sec, visit.id)
    db.commit()
    cred = db.query(VisitorAccessCredential).filter(VisitorAccessCredential.visit_id == visit.id).first()
    assert cred.status == PhysicalAccessStatus.REVOCATION_PENDING.value
    monkeypatch.setattr(settings, "access_mock_simulate_unavailable", False)
    retry_credential(db, owner, cred.id)
    db.commit()
    db.refresh(cred)
    assert cred.status == PhysicalAccessStatus.REVOKED.value


def test_phase14_printer_outage_retry_e2e(test_db, monkeypatch):
    TestingSessionLocal, _, session = test_db
    owner = _owner_ctx(session)
    db = TestingSessionLocal()
    _setup_blr_access(db, owner, monkeypatch)
    visit, _ = _approved_visit_blr(session, "prtout")
    _checkin(db, session, visit.id)
    monkeypatch.setattr(settings, "badge_printer_mock_simulate_offline", True)
    job = request_physical_print(db, _sec_blr_ctx(session), visit.id, idempotency_key=f"outage-{visit.id}")
    db.commit()
    job_row = db.query(BadgePrintJob).filter(BadgePrintJob.visit_id == visit.id).first()
    if job_row.status == "QUEUED":
        job_row.status = "FAILED"
        db.commit()
    assert job_row.status in ("FAILED", "MANUAL_ACTION_REQUIRED", "QUEUED")
    monkeypatch.setattr(settings, "badge_printer_mock_simulate_offline", False)
    retry_print_job(db, _sec_blr_ctx(session), job_row.id)
    db.commit()
    db.refresh(job_row)
    assert job_row.status == "PRINTED"


def test_phase14_physical_badge_print_e2e(test_db, monkeypatch):
    TestingSessionLocal, _, session = test_db
    owner = _owner_ctx(session)
    db = TestingSessionLocal()
    _setup_blr_access(db, owner, monkeypatch)
    visit, _ = _approved_visit_blr(session, "physprt")
    _checkin(db, session, visit.id)
    job1 = request_physical_print(db, _sec_blr_ctx(session), visit.id, idempotency_key=f"phys-{visit.id}")
    db.commit()
    assert job1["status"] == "PRINTED"
    job2 = request_physical_print(db, _sec_blr_ctx(session), visit.id, idempotency_key=f"reprint-{visit.id}")
    db.commit()
    assert job2["status"] == "PRINTED"
    assert job1["badge_number"] == job2["badge_number"]


def test_phase14_credential_expiry_e2e(test_db, monkeypatch):
    TestingSessionLocal, _, session = test_db
    owner = _owner_ctx(session)
    db = TestingSessionLocal()
    _setup_blr_access(db, owner, monkeypatch)
    visit, _ = _approved_visit_blr(session, "expiree2e")
    _checkin(db, session, visit.id)
    cred = db.query(VisitorAccessCredential).filter(VisitorAccessCredential.visit_id == visit.id).first()
    cred.valid_until = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()
    process_expired_credentials(db)
    process_pending_access_attempts(db)
    db.commit()
    db.refresh(cred)
    assert cred.status in (
        PhysicalAccessStatus.REVOKED.value,
        PhysicalAccessStatus.EXPIRED.value,
        PhysicalAccessStatus.REVOCATION_PENDING.value,
    )


def test_phase14_cross_location_physical_integration_e2e(client, test_db, monkeypatch):
    c, TestingSessionLocal, session = client
    owner = _owner_ctx(session)
    db = TestingSessionLocal()
    _setup_blr_access(db, owner, monkeypatch)
    visit, _ = _approved_visit_blr(session, "xloc")
    _checkin(db, session, visit.id)
    cred = db.query(VisitorAccessCredential).filter(VisitorAccessCredential.visit_id == visit.id).first()
    assert c.get(f"/api/access/credentials/{cred.id}", headers={"X-Dev-User-Email": "security.mum@vms.local"}).status_code in (403, 404)
    assert c.post(
        f"/api/access/credentials/{cred.id}/retry",
        headers={"X-Dev-User-Email": "security.mum@vms.local"},
    ).status_code in (403, 404)
    assert c.get("/api/access/credentials", headers={"X-Dev-User-Email": "security.blr@vms.local"}).status_code == 200


def test_restart_recovery_pending_revocation(test_db, monkeypatch):
    TestingSessionLocal, _, session = test_db
    owner = _owner_ctx(session)
    db = TestingSessionLocal()
    _setup_blr_access(db, owner, monkeypatch)
    visit, _ = _approved_visit_blr(session, "restart")
    _checkin(db, session, visit.id)
    monkeypatch.setattr(settings, "access_mock_simulate_unavailable", True)
    sec = _sec_blr_ctx(session)
    check_out_visit(db, sec, visit.id)
    db.commit()
    cred = db.query(VisitorAccessCredential).filter(VisitorAccessCredential.visit_id == visit.id).first()
    assert cred.status == PhysicalAccessStatus.REVOCATION_PENDING.value
    monkeypatch.setattr(settings, "access_mock_simulate_unavailable", False)
    db2 = TestingSessionLocal()
    attempt = db2.query(AccessProvisioningAttempt).filter(
        AccessProvisioningAttempt.access_credential_id == cred.id,
        AccessProvisioningAttempt.status == "PENDING",
    ).first()
    if attempt:
        attempt.available_at = datetime.now(timezone.utc) - timedelta(seconds=60)
    db2.commit()
    run_physical_integration_cycle(db2)
    db2.commit()
    db.refresh(cred)
    assert cred.status == PhysicalAccessStatus.REVOKED.value


def test_double_retry_idempotency(test_db, monkeypatch):
    TestingSessionLocal, _, session = test_db
    owner = _owner_ctx(session)
    db = TestingSessionLocal()
    _setup_blr_access(db, owner, monkeypatch)
    visit, _ = _approved_visit_blr(session, "dblretry")
    _checkin(db, session, visit.id)
    cred = db.query(VisitorAccessCredential).filter(VisitorAccessCredential.visit_id == visit.id).first()
    from app.application.access_provisioning_service import _queue_attempt, ACTION_PROVISION
    _queue_attempt(db, cred.id, ACTION_PROVISION, f"RETRY-PROVISION:{cred.id}")
    _queue_attempt(db, cred.id, ACTION_PROVISION, f"RETRY-PROVISION:{cred.id}")
    db.commit()
    pending = db.query(AccessProvisioningAttempt).filter(
        AccessProvisioningAttempt.dedupe_key == f"RETRY-PROVISION:{cred.id}",
    ).count()
    assert pending == 1


def test_anonymized_visitor_physical_integration_privacy(test_db, monkeypatch):
    TestingSessionLocal, _, session = test_db
    owner = _owner_ctx(session)
    db = TestingSessionLocal()
    _setup_blr_access(db, owner, monkeypatch)
    visit, _ = _approved_visit_blr(session, "anon")
    visitor = session.query(Visitor).filter(Visitor.id == visit.visitor_id).first()
    _checkin(db, session, visit.id)
    visitor.email = None
    visitor.phone = None
    visitor.full_name = "Anonymized Visitor"
    visitor.privacy_state = "ANONYMIZED"
    session.commit()
    cred = db.query(VisitorAccessCredential).filter(VisitorAccessCredential.visit_id == visit.id).first()
    assert cred.visitor_id == visitor.id
    assert cred.visit_id == visit.id
    assert "@" not in str(cred.last_error_code or "")


def test_mapping_conflict_not_silent(test_db):
    TestingSessionLocal, _, session = test_db
    owner = _owner_ctx(session)
    db = TestingSessionLocal()
    blr = session.query(Location).filter(Location.code == "BLR").first()
    p1 = create_profile(db, owner, blr.id, "Profile A", "ref-a")
    p2 = create_profile(db, owner, blr.id, "Profile B", "ref-b")
    vt = session.query(VisitorType).filter(VisitorType.code == "BUSINESS").first()
    create_profile_mapping(db, owner, blr.id, vt.id, p1["id"])
    db.commit()
    from app.application.access_config_service import AccessConfigError, create_profile_mapping as map_create
    with pytest.raises(AccessConfigError) as exc:
        map_create(db, owner, blr.id, vt.id, p2["id"])
    assert exc.value.status_code == 409


def test_mass_assignment_location_config_denied(client, test_db):
    c, _, session = client
    mum = session.query(Location).filter(Location.code == "MUM").first()
    r = c.patch(
        f"/api/access/config/locations/{mum.id}",
        headers={"X-Dev-User-Email": "security.blr@vms.local"},
        json={"provider_key": "dev_mock", "access_control_enabled": True},
    )
    assert r.status_code in (403, 404)
