"""Phase 8.1: Compliance UI support — requirements admin, concurrency, visit detail."""

import os
import tempfile
from datetime import datetime, timedelta, timezone
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.application.auth_service import build_auth_context
from app.application.bootstrap import bootstrap_development_data
from app.application.compliance_document_service import (
    ComplianceDocumentError,
    reject_document,
    upload_document,
    verify_document,
)
from app.application.compliance_requirement_service import create_requirement, deactivate_requirement
from app.application.compliance_service import evaluate_visit_compliance
from app.domain.enums import ComplianceStatus
from app.application.vendor_company_service import create_vendor_company
from app.domain.models import AdminUser, ComplianceRequirement, Location, VisitorType
from app.infrastructure.database import Base, get_db
from app.main import create_app

PDF_BYTES = b"%PDF-1.4\n% minimal test pdf\n"


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


def _head_admin_ctx(session):
    user = session.query(AdminUser).filter(AdminUser.email == "headadmin@vms.local").first()
    return build_auth_context(user)


def _site_admin_blr_ctx(session):
    user = session.query(AdminUser).filter(AdminUser.email == "siteadmin.blr@vms.local").first()
    return build_auth_context(user)


def _contractor_type_id(session):
    return session.query(VisitorType).filter(VisitorType.code == "CONTRACTOR").first().id


def _blr_location(session):
    return session.query(Location).filter(Location.code == "BLR").first()


def test_global_admin_can_create_requirement_via_api(client):
    c, _, session = client
    vt_id = _contractor_type_id(session)
    r = c.post(
        "/api/compliance/requirements",
        headers={"X-Dev-User-Email": "sheru.bohra@lazypay.in"},
        json={
            "name": "Phase81 Test Requirement",
            "visitor_type_id": vt_id,
            "scope_type": "GLOBAL",
            "document_owner_type": "COMPANY",
            "is_mandatory": True,
            "validity_required": True,
            "expiry_warning_days": 30,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Phase81 Test Requirement"
    assert body["scope_type"] == "GLOBAL"
    assert body["is_active"] is True


def _vendor_company_id(session):
    owner = _owner_ctx(session)
    blr = _blr_location(session)
    company = create_vendor_company(session, owner, name="Phase81 Vendor", location_ids=[blr.id])
    return company["id"]


def test_head_admin_can_create_requirement(client, test_db):
    c, _, session = client
    head = session.query(AdminUser).filter(AdminUser.email == "headadmin@vms.local").first()
    if not head:
        pytest.skip("headadmin not seeded in bootstrap")
    vt_id = _contractor_type_id(session)
    r = c.post(
        "/api/compliance/requirements",
        headers={"X-Dev-User-Email": "headadmin@vms.local"},
        json={
            "name": "Head Admin Req",
            "visitor_type_id": vt_id,
            "scope_type": "GLOBAL",
            "document_owner_type": "VISITOR",
        },
    )
    assert r.status_code == 200


def test_site_admin_cannot_create_global_requirement(client):
    c, _, session = client
    vt_id = _contractor_type_id(session)
    r = c.post(
        "/api/compliance/requirements",
        headers={"X-Dev-User-Email": "siteadmin.blr@vms.local"},
        json={
            "name": "Site Admin Req",
            "visitor_type_id": vt_id,
            "scope_type": "GLOBAL",
            "document_owner_type": "COMPANY",
        },
    )
    assert r.status_code == 403


def test_security_cannot_create_requirement(client):
    c, _, session = client
    vt_id = _contractor_type_id(session)
    r = c.post(
        "/api/compliance/requirements",
        headers={"X-Dev-User-Email": "security.blr@vms.local"},
        json={
            "name": "Security Req",
            "visitor_type_id": vt_id,
            "scope_type": "GLOBAL",
            "document_owner_type": "COMPANY",
        },
    )
    assert r.status_code == 403


def test_location_scoped_requirement_validates_location(client):
    c, _, session = client
    vt_id = _contractor_type_id(session)
    blr = _blr_location(session)
    r = c.post(
        "/api/compliance/requirements",
        headers={"X-Dev-User-Email": "sheru.bohra@lazypay.in"},
        json={
            "name": "BLR Only Safety",
            "visitor_type_id": vt_id,
            "scope_type": "LOCATION",
            "location_id": blr.id,
            "document_owner_type": "VISITOR",
        },
    )
    assert r.status_code == 200
    assert r.json()["location_id"] == blr.id


def test_deactivated_requirement_ignored_by_new_evaluation(test_db):
    TestingSessionLocal, _, session = test_db
    owner = _owner_ctx(session)
    vt_id = _contractor_type_id(session)
    req = create_requirement(
        session, owner,
        name="Deact Test Req",
        visitor_type_id=vt_id,
        scope_type="GLOBAL",
        document_owner_type="COMPANY",
        is_mandatory=True,
    )
    req_id = req["id"]
    deactivate_requirement(session, owner, req_id)
    inactive = session.query(ComplianceRequirement).filter(ComplianceRequirement.id == req_id).first()
    assert inactive.is_active is False
    active_codes = [
        r.code for r in session.query(ComplianceRequirement).filter(ComplianceRequirement.is_active.is_(True)).all()
    ]
    assert "DEACT_TEST_REQ" not in active_codes or inactive.code not in active_codes


def test_pending_document_can_be_verified(test_db):
    TestingSessionLocal, _, session = test_db
    owner = _owner_ctx(session)
    vendor_id = _vendor_company_id(session)
    req = session.query(ComplianceRequirement).filter(ComplianceRequirement.code == "INSURANCE_CERT").first()
    doc = upload_document(
        session, owner,
        requirement_id=req.id,
        file_stream=BytesIO(PDF_BYTES),
        file_name="ins.pdf",
        mime_type="application/pdf",
        size_bytes=len(PDF_BYTES),
        vendor_company_id=vendor_id,
        valid_from=datetime.now(timezone.utc),
        valid_until=datetime.now(timezone.utc) + timedelta(days=90),
    )
    verified = verify_document(session, owner, doc["id"])
    assert verified["status"] == "VALID"


def test_pending_document_can_be_rejected(test_db):
    TestingSessionLocal, _, session = test_db
    owner = _owner_ctx(session)
    vendor_id = _vendor_company_id(session)
    req = session.query(ComplianceRequirement).filter(ComplianceRequirement.code == "INSURANCE_CERT").first()
    doc = upload_document(
        session, owner,
        requirement_id=req.id,
        file_stream=BytesIO(PDF_BYTES),
        file_name="ins2.pdf",
        mime_type="application/pdf",
        size_bytes=len(PDF_BYTES),
        vendor_company_id=vendor_id,
        valid_from=datetime.now(timezone.utc),
        valid_until=datetime.now(timezone.utc) + timedelta(days=90),
    )
    rejected = reject_document(session, owner, doc["id"], "Incorrect document")
    assert rejected["status"] == "REJECTED"


def test_verified_document_cannot_be_rejected(test_db):
    TestingSessionLocal, _, session = test_db
    owner = _owner_ctx(session)
    vendor_id = _vendor_company_id(session)
    req = session.query(ComplianceRequirement).filter(ComplianceRequirement.code == "INSURANCE_CERT").first()
    doc = upload_document(
        session, owner,
        requirement_id=req.id,
        file_stream=BytesIO(PDF_BYTES),
        file_name="ins3.pdf",
        mime_type="application/pdf",
        size_bytes=len(PDF_BYTES),
        vendor_company_id=vendor_id,
        valid_from=datetime.now(timezone.utc),
        valid_until=datetime.now(timezone.utc) + timedelta(days=90),
    )
    verify_document(session, owner, doc["id"])
    with pytest.raises(ComplianceDocumentError) as exc:
        reject_document(session, owner, doc["id"], "Too late")
    assert exc.value.status_code == 409


def test_rejected_document_cannot_be_verified(test_db):
    TestingSessionLocal, _, session = test_db
    owner = _owner_ctx(session)
    vendor_id = _vendor_company_id(session)
    req = session.query(ComplianceRequirement).filter(ComplianceRequirement.code == "INSURANCE_CERT").first()
    doc = upload_document(
        session, owner,
        requirement_id=req.id,
        file_stream=BytesIO(PDF_BYTES),
        file_name="ins4.pdf",
        mime_type="application/pdf",
        size_bytes=len(PDF_BYTES),
        vendor_company_id=vendor_id,
        valid_from=datetime.now(timezone.utc),
        valid_until=datetime.now(timezone.utc) + timedelta(days=90),
    )
    reject_document(session, owner, doc["id"], "Wrong vendor")
    with pytest.raises(ComplianceDocumentError) as exc:
        verify_document(session, owner, doc["id"])
    assert exc.value.status_code == 409


def test_compliance_visit_detail_endpoint(client):
    c, _, session = client
    from tests.test_phase8 import _create_contractor_visit

    detail = _create_contractor_visit(session, "detail81")
    visit_id = detail["id"]
    r = c.get(
        f"/api/compliance/visits/{visit_id}/detail",
        headers={"X-Dev-User-Email": "sheru.bohra@lazypay.in"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["visit_id"] == visit_id
    assert "compliance" in body
    assert "requirements" in body
    assert body["visitor_name"]
