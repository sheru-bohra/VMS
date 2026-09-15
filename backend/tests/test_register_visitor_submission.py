"""End-to-end Register Visitor submission matrix."""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.application.auth_service import build_auth_context
from app.application.bootstrap import bootstrap_development_data
from app.application.invitation_service import InvitationError, create_advance_visit
from app.application.register_visitor_policy import get_register_visitor_policy
from app.application.vendor_company_service import create_vendor_company
from app.domain.enums import VisitStatus
from app.domain.models import (
    AdminUser,
    AuditEvent,
    Host,
    HostLocationAssignment,
    Location,
    VendorCompanyLocation,
    Visit,
    VisitorType,
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


def _blr_host_id(session):
    loc = session.query(Location).filter(Location.code == "BLR").first()
    ha = session.query(HostLocationAssignment).filter(HostLocationAssignment.location_id == loc.id).first()
    return ha.host_id, loc.id


def _owner_ctx(session):
    user = session.query(AdminUser).filter(AdminUser.email == "sheru.bohra@lazypay.in").first()
    return build_auth_context(user)


def _future_visit_date():
    return (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")


def _base_payload(host_id: int | None, loc_id: int, visitor_type: str, mobile: str, **extra):
    fields = dict(extra)
    payload = {
        "location_id": loc_id,
        "visitor_type": visitor_type,
        "full_name": fields.pop("full_name", f"MOCK {visitor_type}"),
        "mobile": mobile,
        "email": fields.pop("email", "mock@example.invalid"),
        "company": fields.pop("company", "MOCK COMPANY"),
        "visit_date": _future_visit_date(),
        "arrival_time": "10:00",
        "departure_time": "11:00",
        "expected_duration_minutes": 60,
        "purpose": fields.pop("purpose", "MOCK purpose"),
        "policy_accepted": True,
    }
    if "host_id" in fields:
        explicit_host = fields.pop("host_id")
        if explicit_host is not None:
            payload["host_id"] = explicit_host
    elif host_id is not None:
        payload["host_id"] = host_id
    payload.update(fields)
    return payload


def _post(client, payload, email="sheru.bohra@lazypay.in"):
    return client.post("/api/invitations", json=payload, headers={"X-Dev-User-Email": email})


def _assert_success(session, response, expected_company: str | None = None):
    assert response.status_code == 200, response.text
    body = response.json()
    visit = session.get(Visit, body["id"])
    assert visit is not None
    assert visit.status == VisitStatus.PENDING_APPROVAL.value
    assert visit.created_by_user_id is not None
    creator = session.get(AdminUser, visit.created_by_user_id)
    assert creator is not None
    assert creator.email == "sheru.bohra@lazypay.in"
    if expected_company is not None:
        assert visit.visitor.company == expected_company
    audit = (
        session.query(AuditEvent)
        .filter(AuditEvent.entity_type == "visit", AuditEvent.entity_id == str(visit.id))
        .all()
    )
    assert any(a.action == "ADVANCE_VISIT_CREATED" for a in audit)
    return body, visit


@pytest.mark.parametrize(
    "visitor_type,mobile,extra",
    [
        ("BUSINESS", "9876500001", {"company": "Mock Business Pvt Ltd", "purpose": "Business Meeting"}),
        ("PARTNER", "9876500002", {"company": "Partner Test Corp"}),
        ("VIP", "9876500003", {}),
        ("INTERVIEW", "9876500004", {"email": "candidate@example.invalid"}),
        ("DELIVERY", "9876500005", {"company": "Mock Courier Services", "host_id": None}),
        ("EVENT", "9876500006", {}),
        ("OTHER", "9876500010", {}),
    ],
)
def test_register_visitor_mock_types(client, visitor_type, mobile, extra):
    c, TestingSessionLocal, session = client
    host_id, loc_id = _blr_host_id(session)
    assert host_id is not None, "BLR host assignment missing in test bootstrap"
    extra_copy = dict(extra)
    explicit_host = extra_copy.pop("host_id", "___missing___")
    effective_host = host_id if explicit_host == "___missing___" else explicit_host
    payload = _base_payload(effective_host, loc_id, visitor_type, mobile, **extra_copy)
    response = _post(c, payload)
    with TestingSessionLocal() as read_session:
        company = extra.get("company") or None
        if company == "":
            company = None
        _assert_success(read_session, response, expected_company=company)


def test_register_visitor_vendor_free_text_company(client):
    c, TestingSessionLocal, session = client
    host_id, loc_id = _blr_host_id(session)
    payload = _base_payload(
        host_id,
        loc_id,
        "VENDOR",
        "9876500007",
        full_name="Mock Vendor",
        company="UNREGISTERED MOCK COMPANY",
        purpose="Maintenance",
        work_purpose="Maintenance Test",
        po_work_order_reference="MOCK-PO-1001",
        safety_acknowledged=True,
        safety_induction_completed=True,
        govt_id_type="PASSPORT",
        govt_id_number="TEST-ID-1001",
        signature_storage_key="mock-signature-key",
        departure_time="12:00",
    )
    response = _post(c, payload)
    with TestingSessionLocal() as read_session:
        body, visit = _assert_success(read_session, response, "UNREGISTERED MOCK COMPANY")
        assert visit.vendor_visit_details is None
        meta = visit.registration_metadata_json or {}
        assert meta.get("govt_id_masked") == "••••1001"
        assert body["registration_reference"].startswith("VMS-")


def test_register_visitor_contractor_mock(client):
    c, TestingSessionLocal, session = client
    host_id, loc_id = _blr_host_id(session)
    payload = _base_payload(
        host_id,
        loc_id,
        "CONTRACTOR",
        "9876500008",
        full_name="Mock Contractor",
        company="Mock Contractor Services",
        purpose="Work",
        work_purpose="Site work",
        po_work_order_reference="MOCK-WO-2001",
        safety_acknowledged=True,
        safety_induction_completed=True,
        govt_id_type="PASSPORT",
        govt_id_number="TEST-ID-2001",
        signature_storage_key="mock-signature-key",
        departure_time="12:00",
    )
    response = _post(c, payload)
    with TestingSessionLocal() as read_session:
        _assert_success(read_session, response, "Mock Contractor Services")


def test_register_visitor_service_maintenance_mock(client):
    c, TestingSessionLocal, session = client
    host_id, loc_id = _blr_host_id(session)
    payload = _base_payload(
        host_id,
        loc_id,
        "SERVICE",
        "9876500009",
        full_name="Mock Service Person",
        company="Mock Maintenance Services",
        purpose="AC repair",
        work_purpose="AC repair",
        po_work_order_reference="MOCK-WO-3001",
        safety_acknowledged=True,
        safety_induction_completed=True,
        govt_id_type="PASSPORT",
        govt_id_number="TEST-ID-3001",
        signature_storage_key="mock-signature-key",
        departure_time="12:00",
    )
    response = _post(c, payload)
    with TestingSessionLocal() as read_session:
        _assert_success(read_session, response, "Mock Maintenance Services")


def test_register_visitor_vendor_optional_company_match(client):
    c, TestingSessionLocal, session = client
    host_id, loc_id = _blr_host_id(session)
    ctx = _owner_ctx(session)
    company = create_vendor_company(session, ctx, name="Matched Vendor Ltd", location_ids=[loc_id])
    session.add(
        VendorCompanyLocation(vendor_company_id=company["id"], location_id=loc_id, is_active=True)
    )
    session.commit()
    payload = _base_payload(
        host_id,
        loc_id,
        "VENDOR",
        "9876500011",
        full_name="Mock Matched Vendor",
        company="Matched Vendor Ltd",
        purpose="Maintenance",
        work_purpose="Repair",
        po_work_order_reference="MOCK-PO-2002",
        safety_acknowledged=True,
        safety_induction_completed=True,
        govt_id_type="PASSPORT",
        govt_id_number="TEST-ID-4001",
        signature_storage_key="mock-signature-key",
        departure_time="12:00",
    )
    response = _post(c, payload)
    with TestingSessionLocal() as read_session:
        _, visit = _assert_success(read_session, response, "Matched Vendor Ltd")
        assert visit.vendor_visit_details is not None
        assert visit.vendor_visit_details.vendor_company_id == company["id"]


def test_register_visitor_validation_errors_are_4xx(client):
    c, _, session = client
    host_id, loc_id = _blr_host_id(session)
    bad_mobile = _base_payload(host_id, loc_id, "BUSINESS", "98765000")
    response = _post(c, bad_mobile)
    assert response.status_code == 422

    missing_policy = _base_payload(host_id, loc_id, "BUSINESS", "9876500020", policy_accepted=False)
    response = _post(c, missing_policy)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "policy_required"

    missing_company = _base_payload(host_id, loc_id, "BUSINESS", "9876500021", company="")
    response = _post(c, missing_company)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "company_required"


def test_register_visitor_location_authorization(client):
    c, _, session = client
    host_id, _ = _blr_host_id(session)
    mum = session.query(Location).filter(Location.code == "MUM").first()
    payload = _base_payload(host_id, mum.id, "BUSINESS", "9876500022")
    response = _post(c, payload, email="siteadmin.blr@vms.local")
    assert response.status_code == 403


def test_register_visitor_govt_id_without_encryption_key_in_development(test_db, monkeypatch):
    _, _, session = test_db
    host_id, loc_id = _blr_host_id(session)
    ctx = _owner_ctx(session)
    monkeypatch.delenv("DOCUMENT_ENCRYPTION_KEY", raising=False)
    from app.core.config import settings

    monkeypatch.setattr(settings, "document_encryption_key", None)
    monkeypatch.setattr(settings, "app_env", "development")
    result = create_advance_visit(
        session,
        ctx,
        location_id=loc_id,
        visitor_type_code="VENDOR",
        full_name="Mock Vendor",
        mobile="9876500023",
        email="vendor@example.invalid",
        company="UNREGISTERED MOCK COMPANY",
        host_id=host_id,
        visit_date=_future_visit_date(),
        arrival_time="10:00",
        departure_time="12:00",
        expected_duration_minutes=60,
        purpose="Maintenance",
        policy_accepted=True,
        work_purpose="Maintenance Test",
        po_work_order_reference="MOCK-PO-1001",
        safety_acknowledged=True,
        govt_id_type="PASSPORT",
        govt_id_number="TEST-ID-1001",
        signature_storage_key="mock-signature-key",
    )
    visit = session.get(Visit, result["id"])
    meta = visit.registration_metadata_json or {}
    assert meta.get("govt_id_masked") == "••••1001"
    assert "govt_id_encrypted" not in meta


def test_register_visitor_mobile_validation_service(test_db):
    _, _, session = test_db
    host_id, loc_id = _blr_host_id(session)
    ctx = _owner_ctx(session)
    with pytest.raises(InvitationError) as exc:
        create_advance_visit(
            session,
            ctx,
            location_id=loc_id,
            visitor_type_code="BUSINESS",
            full_name="Bad Mobile",
            mobile="98765000",
            email="m@example.invalid",
            company="Co",
            host_id=host_id,
            visit_date=_future_visit_date(),
            arrival_time="10:00",
            expected_duration_minutes=60,
            purpose="Meeting",
            policy_accepted=True,
            departure_time="11:00",
        )
    assert exc.value.code == "invalid_mobile"


def test_register_visitor_policy_matrix_unchanged(test_db):
    _, _, session = test_db
    business = session.query(VisitorType).filter(VisitorType.code == "BUSINESS").first()
    vendor = session.query(VisitorType).filter(VisitorType.code == "VENDOR").first()
    vip = session.query(VisitorType).filter(VisitorType.code == "VIP").first()
    assert get_register_visitor_policy(business).company_required is True
    assert get_register_visitor_policy(vendor).govt_id_required is True
    assert get_register_visitor_policy(vip).govt_id_required is False
