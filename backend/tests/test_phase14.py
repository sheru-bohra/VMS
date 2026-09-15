"""Phase 14 — physical access control and badge printer integration."""

import os
import tempfile
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.application.access_config_service import create_printer, create_profile, create_profile_mapping
from app.application.access_provisioning_service import (
    get_location_access_config,
    process_expired_credentials,
    process_pending_access_attempts,
)
from app.application.auth_service import build_auth_context
from app.application.bootstrap import bootstrap_development_data
from app.application.operations_service import check_in_visit, check_out_visit, mark_arrived, OperationsError
from app.application.compliance_service import evaluate_visit_compliance
from app.application.emergency_roll_call_service import start_emergency
from app.application.watchlist_service import create_watchlist_entry
from app.application.approval_service import approve_visit
from app.application.security_screening_service import screen_visit
from app.application.physical_badge_print_service import request_physical_print
from app.core.config import settings
from app.domain.enums import ComplianceStatus, PhysicalAccessStatus, SecurityClearanceStatus, VisitStatus
from app.domain.models import (
    AdminUser,
    ComplianceDocument,
    Location,
    LocationAccessConfiguration,
    Visitor,
    VisitorAccessCredential,
    VisitorType,
    Visit,
    Host,
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
    owner = session.query(AdminUser).filter(AdminUser.email == "sheru.bohra@lazypay.in").first()
    return build_auth_context(owner)


def _sec_blr_ctx(session):
    user = session.query(AdminUser).filter(AdminUser.email == "security.blr@vms.local").first()
    return build_auth_context(user)


def _setup_blr_access(db, owner_ctx, monkeypatch):
    monkeypatch.setattr(settings, "access_control_enabled", True)
    monkeypatch.setattr(settings, "access_control_provider", "dev_mock")
    monkeypatch.setattr(settings, "badge_printer_enabled", True)
    monkeypatch.setattr(settings, "badge_printer_provider", "dev_mock")
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
    create_printer(
        db, owner_ctx, blr.id, "Reception Printer", "dev_mock", "printer-blr-1", is_default=True,
    )
    db.commit()
    return blr


def _approved_visit_blr(session, suffix="p14"):
    blr = session.query(Location).filter(Location.code == "BLR").first()
    vt = session.query(VisitorType).filter(VisitorType.code == "BUSINESS").first()
    host = session.query(Host).filter(Host.is_development_seed.is_(True)).first()
    visitor = Visitor(
        full_name=f"P14 {suffix}",
        email=f"p14{suffix}@test.com",
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


def test_checkin_disabled_site_no_credential(test_db, monkeypatch):
    monkeypatch.setattr(settings, "access_control_enabled", False)
    TestingSessionLocal, _, session = test_db
    owner = _owner_ctx(session)
    db = TestingSessionLocal()
    visit, _ = _approved_visit_blr(session)
    sec = _sec_blr_ctx(session)
    screen_visit(db, visit.id, trigger="check_in")
    mark_arrived(db, sec, visit.id)
    db.commit()
    check_in_visit(db, sec, visit.id)
    db.commit()
    cred = db.query(VisitorAccessCredential).filter(VisitorAccessCredential.visit_id == visit.id).first()
    assert cred is None


def test_checkin_enabled_creates_active_credential(test_db, monkeypatch):
    TestingSessionLocal, _, session = test_db
    owner = _owner_ctx(session)
    db = TestingSessionLocal()
    _setup_blr_access(db, owner, monkeypatch)
    visit, _ = _approved_visit_blr(session, "active")
    sec = _sec_blr_ctx(session)
    screen_visit(db, visit.id, trigger="check_in")
    mark_arrived(db, sec, visit.id)
    db.commit()
    check_in_visit(db, sec, visit.id)
    db.commit()
    cred = db.query(VisitorAccessCredential).filter(VisitorAccessCredential.visit_id == visit.id).first()
    assert cred is not None
    assert cred.status == PhysicalAccessStatus.ACTIVE.value
    assert cred.valid_until is not None
    assert cred.provider_credential_reference


def test_checkin_idempotent_no_duplicate_credential(test_db, monkeypatch):
    TestingSessionLocal, _, session = test_db
    owner = _owner_ctx(session)
    db = TestingSessionLocal()
    _setup_blr_access(db, owner, monkeypatch)
    visit, _ = _approved_visit_blr(session, "dup")
    sec = _sec_blr_ctx(session)
    screen_visit(db, visit.id, trigger="check_in")
    mark_arrived(db, sec, visit.id)
    db.commit()
    check_in_visit(db, sec, visit.id)
    db.commit()
    check_in_visit(db, sec, visit.id)
    db.commit()
    count = db.query(VisitorAccessCredential).filter(VisitorAccessCredential.visit_id == visit.id).count()
    assert count == 1


def test_provider_failure_checkin_still_onsite(test_db, monkeypatch):
    TestingSessionLocal, _, session = test_db
    owner = _owner_ctx(session)
    db = TestingSessionLocal()
    _setup_blr_access(db, owner, monkeypatch)
    monkeypatch.setattr(settings, "access_mock_simulate_unavailable", True)
    visit, _ = _approved_visit_blr(session, "fail")
    sec = _sec_blr_ctx(session)
    screen_visit(db, visit.id, trigger="check_in")
    mark_arrived(db, sec, visit.id)
    db.commit()
    check_in_visit(db, sec, visit.id)
    db.commit()
    visit_row = db.query(Visit).filter(Visit.id == visit.id).first()
    assert visit_row.status == VisitStatus.ONSITE.value
    cred = db.query(VisitorAccessCredential).filter(VisitorAccessCredential.visit_id == visit.id).first()
    assert cred.status in (PhysicalAccessStatus.PENDING.value, PhysicalAccessStatus.FAILED.value)


def test_checkout_revokes_credential(test_db, monkeypatch):
    TestingSessionLocal, _, session = test_db
    owner = _owner_ctx(session)
    db = TestingSessionLocal()
    _setup_blr_access(db, owner, monkeypatch)
    visit, _ = _approved_visit_blr(session, "checkout")
    sec = _sec_blr_ctx(session)
    screen_visit(db, visit.id, trigger="check_in")
    mark_arrived(db, sec, visit.id)
    db.commit()
    check_in_visit(db, sec, visit.id)
    db.commit()
    check_out_visit(db, sec, visit.id)
    db.commit()
    cred = db.query(VisitorAccessCredential).filter(VisitorAccessCredential.visit_id == visit.id).first()
    assert cred.status == PhysicalAccessStatus.REVOKED.value


def test_physical_print_success(test_db, monkeypatch):
    TestingSessionLocal, _, session = test_db
    owner = _owner_ctx(session)
    db = TestingSessionLocal()
    _setup_blr_access(db, owner, monkeypatch)
    visit, _ = _approved_visit_blr(session, "print")
    sec = _sec_blr_ctx(session)
    screen_visit(db, visit.id, trigger="check_in")
    mark_arrived(db, sec, visit.id)
    db.commit()
    check_in_visit(db, sec, visit.id)
    db.commit()
    job = request_physical_print(db, sec, visit.id, idempotency_key=f"print-{visit.id}")
    db.commit()
    assert job["status"] == "PRINTED"


def test_cross_location_credential_denied(client, test_db):
    c, _, _ = client
    _, _, session = test_db
    mum = session.query(Location).filter(Location.code == "MUM").first()
    visitor = Visitor(full_name="Mum Access", privacy_state="ACTIVE")
    session.add(visitor)
    session.flush()
    visit = Visit(visitor_id=visitor.id, location_id=mum.id, status=VisitStatus.ONSITE.value)
    session.add(visit)
    session.flush()
    cred = VisitorAccessCredential(
        visit_id=visit.id,
        visitor_id=visitor.id,
        location_id=mum.id,
        status=PhysicalAccessStatus.ACTIVE.value,
        provider_key="dev_mock",
        provider_credential_reference="ref-mum",
    )
    session.add(cred)
    session.commit()
    r = c.get(f"/api/access/credentials/{cred.id}", headers={"X-Dev-User-Email": "security.blr@vms.local"})
    assert r.status_code in (403, 404)


def test_production_rejects_dev_mock_access(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "access_control_enabled", True)
    monkeypatch.setattr(settings, "access_control_provider", "dev_mock")
    monkeypatch.setattr(settings, "auth_mode", "vms_native")
    monkeypatch.setattr(settings, "vms_native_auth_enabled", True)
    monkeypatch.setattr(settings, "dev_auth_enabled", False)
    monkeypatch.setattr(settings, "email_provider", "smtp")
    monkeypatch.setattr(settings, "ai_enabled", False)
    monkeypatch.setattr(settings, "public_app_base_url", "https://vms.example")
    from cryptography.fernet import Fernet
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(settings, "audit_integrity_key", key)
    monkeypatch.setattr(settings, "vms_data_encryption_key", key)
    monkeypatch.setattr(settings, "document_encryption_key", key)
    monkeypatch.setattr(settings, "rate_limit_backend", "database")
    monkeypatch.setattr(settings, "file_scanner_provider", "clamav")
    with pytest.raises(RuntimeError, match="ACCESS_CONTROL_PROVIDER"):
        settings.validate_environment()


def test_credential_expiry(test_db, monkeypatch):
    TestingSessionLocal, _, session = test_db
    owner = _owner_ctx(session)
    db = TestingSessionLocal()
    _setup_blr_access(db, owner, monkeypatch)
    visit, blr = _approved_visit_blr(session, "expire")
    sec = _sec_blr_ctx(session)
    screen_visit(db, visit.id, trigger="check_in")
    mark_arrived(db, sec, visit.id)
    db.commit()
    check_in_visit(db, sec, visit.id)
    db.commit()
    cred = db.query(VisitorAccessCredential).filter(VisitorAccessCredential.visit_id == visit.id).first()
    cred.valid_until = datetime.now(timezone.utc) - timedelta(minutes=5)
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


def test_security_blocked_checkin_no_credential(test_db, monkeypatch):
    TestingSessionLocal, _, session = test_db
    owner = _owner_ctx(session)
    db = TestingSessionLocal()
    _setup_blr_access(db, owner, monkeypatch)
    visit, _ = _approved_visit_blr(session, "secblk")
    visitor = session.query(Visitor).filter(Visitor.id == visit.visitor_id).first()
    create_watchlist_entry(
        session,
        owner,
        scope_type="GLOBAL",
        full_name=visitor.full_name,
        mobile=visitor.phone,
        reason_code="PREVIOUS_SECURITY_INCIDENT",
        action_level="BLOCK",
        valid_from=datetime.now(timezone.utc),
    )
    session.commit()
    sec = _sec_blr_ctx(session)
    mark_arrived(db, sec, visit.id)
    db.commit()
    with pytest.raises(OperationsError) as exc:
        check_in_visit(db, sec, visit.id)
    assert "SECURITY" in exc.value.code
    cred = db.query(VisitorAccessCredential).filter(VisitorAccessCredential.visit_id == visit.id).first()
    assert cred is None


def test_compliance_blocked_checkin_no_credential(test_db, monkeypatch):
    from tests.test_phase8 import (
        _align_visit_schedule,
        _create_contractor_visit,
        _req_by_code,
        _verify_all_mandatory,
    )

    TestingSessionLocal, _, session = test_db
    owner = _owner_ctx(session)
    db = TestingSessionLocal()
    _setup_blr_access(db, owner, monkeypatch)
    detail = _create_contractor_visit(session, "compblk")
    visit_id = detail["id"]
    visit = _align_visit_schedule(session, visit_id)
    sec = _sec_blr_ctx(session)
    _verify_all_mandatory(session, owner, visit_id, detail["vendor_company_id"], visit.visitor_id)
    evaluate_visit_compliance(session, visit_id, trigger="test")
    session.commit()
    approve_visit(db, owner, visit_id)
    doc = session.query(ComplianceDocument).filter(
        ComplianceDocument.vendor_company_id == detail["vendor_company_id"],
        ComplianceDocument.requirement_id == _req_by_code(session, "INSURANCE_CERT").id,
    ).first()
    doc.valid_until = datetime.now(timezone.utc) - timedelta(days=1)
    doc.status = "EXPIRED"
    session.commit()
    mark_arrived(db, sec, visit_id)
    db.commit()
    with pytest.raises(OperationsError) as exc:
        check_in_visit(db, sec, visit_id)
    assert "COMPLIANCE" in exc.value.code
    cred = db.query(VisitorAccessCredential).filter(VisitorAccessCredential.visit_id == visit_id).first()
    assert cred is None


def test_emergency_blocked_checkin_no_credential(test_db, monkeypatch):
    TestingSessionLocal, _, session = test_db
    owner = _owner_ctx(session)
    db = TestingSessionLocal()
    _setup_blr_access(db, owner, monkeypatch)
    blr = db.query(Location).filter(Location.code == "BLR").first()
    start_emergency(session, owner, blr.id, "EMERGENCY")
    visit, _ = _approved_visit_blr(session, "emgblk")
    sec = _sec_blr_ctx(session)
    screen_visit(db, visit.id, trigger="check_in")
    mark_arrived(db, sec, visit.id)
    db.commit()
    with pytest.raises(OperationsError) as exc:
        check_in_visit(db, sec, visit.id)
    assert exc.value.code == "LOCATION_EMERGENCY_ACTIVE"
    cred = db.query(VisitorAccessCredential).filter(VisitorAccessCredential.visit_id == visit.id).first()
    assert cred is None


def test_missing_profile_mapping_manual_action(test_db, monkeypatch):
    TestingSessionLocal, _, session = test_db
    owner = _owner_ctx(session)
    db = TestingSessionLocal()
    monkeypatch.setattr(settings, "access_control_enabled", True)
    monkeypatch.setattr(settings, "access_control_provider", "dev_mock")
    blr = db.query(Location).filter(Location.code == "BLR").first()
    cfg = get_location_access_config(db, blr.id)
    cfg.access_control_enabled = True
    cfg.provider_key = "dev_mock"
    db.commit()
    visit, _ = _approved_visit_blr(session, "nomap")
    sec = _sec_blr_ctx(session)
    screen_visit(db, visit.id, trigger="check_in")
    mark_arrived(db, sec, visit.id)
    db.commit()
    check_in_visit(db, sec, visit.id)
    db.commit()
    cred = db.query(VisitorAccessCredential).filter(VisitorAccessCredential.visit_id == visit.id).first()
    assert cred is not None
    assert cred.status == PhysicalAccessStatus.MANUAL_ACTION_REQUIRED.value
