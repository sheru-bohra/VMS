"""Phase 8: Vendors, contractors, and compliance validity engine."""

import os
import tempfile
from datetime import datetime, timedelta, timezone
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.application.approval_service import ApprovalError, approve_visit
from app.application.auth_service import build_auth_context
from app.application.bootstrap import bootstrap_development_data
from app.application.compliance_document_service import upload_document, verify_document
from app.application.compliance_service import ComplianceError, evaluate_visit_compliance
from app.application.document_storage import DocumentStorageError, validate_upload
from app.application.operations_service import check_in_visit, check_out_visit, mark_arrived, OperationsError
from app.application.registration_service import create_self_registration
from app.application.security_review_service import resolve_clear
from app.application.security_screening_service import screen_visit
from app.application.vendor_company_service import create_vendor_company, VendorCompanyError
from app.application.vendor_visit_service import create_vendor_visit, VendorVisitError
from app.application.visitor_qr_service import verify_by_token
from app.domain.enums import ComplianceStatus, SecurityClearanceStatus, VisitStatus
from app.domain.models import (
    AdminUser,
    ComplianceDocument,
    ComplianceRequirement,
    HostLocationAssignment,
    Location,
    VendorCompany,
    VendorVisitDetails,
    Visit,
    Visitor,
)
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


def _site_admin_blr_ctx(session):
    user = session.query(AdminUser).filter(AdminUser.email == "siteadmin.blr@vms.local").first()
    return build_auth_context(user)


def _site_admin_mum_ctx(session):
    user = session.query(AdminUser).filter(AdminUser.email == "siteadmin.mum@vms.local").first()
    return build_auth_context(user)


def _security_blr_ctx(session):
    user = session.query(AdminUser).filter(AdminUser.email == "security.blr@vms.local").first()
    return build_auth_context(user)


def _blr_host(session):
    loc = session.query(Location).filter(Location.code == "BLR").first()
    ha = session.query(HostLocationAssignment).filter(HostLocationAssignment.location_id == loc.id).first()
    return ha.host_id, loc


def _mum_host(session):
    loc = session.query(Location).filter(Location.code == "MUM").first()
    ha = session.query(HostLocationAssignment).filter(HostLocationAssignment.location_id == loc.id).first()
    if ha:
        return ha.host_id, loc
    blr_ha = session.query(HostLocationAssignment).first()
    session.add(HostLocationAssignment(host_id=blr_ha.host_id, location_id=loc.id))
    session.commit()
    return blr_ha.host_id, loc


def _close_db(db):
    try:
        db.close()
    except Exception:
        pass


def _near_future_schedule():
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")
    return tomorrow, "10:30"


def _align_visit_schedule(session, visit_id: int, minutes_ahead: int = 30) -> Visit:
    visit = session.get(Visit, visit_id)
    now = datetime.now(timezone.utc)
    visit.scheduled_start = now + timedelta(minutes=minutes_ahead)
    visit.scheduled_end = visit.scheduled_start + timedelta(minutes=60)
    visit.expected_arrival = visit.scheduled_start
    session.commit()
    session.refresh(visit)
    return visit


def _req_by_code(session, code: str) -> ComplianceRequirement:
    return session.query(ComplianceRequirement).filter(ComplianceRequirement.code == code).first()


def _create_vendor_company(session, name: str = "ABC Services", location_code: str = "BLR"):
    ctx = _owner_ctx(session)
    loc = session.query(Location).filter(Location.code == location_code).first()
    return create_vendor_company(session, ctx, name=name, location_ids=[loc.id])


def _upload_doc(
    session,
    ctx,
    requirement_code: str,
    vendor_company_id=None,
    visitor_id=None,
    visit_id=None,
    valid_until=None,
):
    req = _req_by_code(session, requirement_code)
    if valid_until is None:
        valid_until = datetime.now(timezone.utc) + timedelta(days=90)
    return upload_document(
        session,
        ctx,
        requirement_id=req.id,
        file_stream=BytesIO(PDF_BYTES),
        file_name="cert.pdf",
        mime_type="application/pdf",
        size_bytes=len(PDF_BYTES),
        vendor_company_id=vendor_company_id,
        visitor_id=visitor_id,
        valid_from=datetime.now(timezone.utc) - timedelta(days=1),
        valid_until=valid_until,
        visit_id=visit_id,
    )


def _verify_all_mandatory(session, ctx, visit_id, vendor_company_id, visitor_id):
    for code in ("VENDOR_AUTH_LETTER", "INSURANCE_CERT", "SAFETY_TRAINING"):
        doc = _upload_doc(
            session, ctx, code,
            vendor_company_id=vendor_company_id if code != "SAFETY_TRAINING" else None,
            visitor_id=visitor_id if code == "SAFETY_TRAINING" else None,
            visit_id=visit_id,
        )
        verify_document(session, ctx, doc["id"], visit_id=visit_id)


def _create_contractor_visit(session, suffix="1", vendor_company_id=None, mobile=None, email=None, name=None):
    ctx = _owner_ctx(session)
    host_id, loc = _blr_host(session)
    if vendor_company_id is None:
        vendor_company_id = _create_vendor_company(session, f"Vendor Co {suffix}").get("id")
    visit_date, arrival = _near_future_schedule()
    return create_vendor_visit(
        session,
        ctx,
        location_id=loc.id,
        visitor_type_code="CONTRACTOR",
        vendor_company_id=vendor_company_id,
        full_name=name or f"Contractor {suffix}",
        mobile=mobile or f"+91988{suffix}00001",
        email=email or f"contractor{suffix}@test.com",
        host_id=host_id,
        work_purpose="HVAC maintenance",
        visit_date=visit_date,
        arrival_time=arrival,
        expected_duration_minutes=60,
        safety_acknowledged=True,
        po_work_order_reference="PO-12345",
    )


def test_global_admin_can_create_vendor_company(test_db):
    _, _, session = test_db
    detail = _create_vendor_company(session)
    assert detail["name"] == "ABC Services"
    assert detail["is_active"] is True
    assert any(l["code"] == "BLR" for l in detail["locations"])


def test_security_cannot_create_vendor_company(test_db):
    _, _, session = test_db
    ctx = _security_blr_ctx(session)
    loc = session.query(Location).filter(Location.code == "BLR").first()
    with pytest.raises(VendorCompanyError) as exc:
        create_vendor_company(session, ctx, name="Blocked Co", location_ids=[loc.id])
    assert exc.value.status_code == 403


def test_duplicate_vendor_company_warning(test_db):
    _, _, session = test_db
    first = _create_vendor_company(session, "ABC Services")
    from app.application.compliance_service import find_duplicate_vendor_companies
    matches = find_duplicate_vendor_companies(session, "ABC Services")
    assert any(m.id == first["id"] for m in matches)
    dup = _create_vendor_company(session, "ABC Service Pvt Ltd")
    assert dup["name"] == "ABC Service Pvt Ltd"


def test_inactive_vendor_cannot_be_used_for_visit(test_db):
    _, _, session = test_db
    ctx = _owner_ctx(session)
    detail = _create_vendor_company(session, "Inactive Vendor")
    company = session.query(VendorCompany).filter(VendorCompany.id == detail["id"]).first()
    company.is_active = False
    session.commit()
    host_id, loc = _blr_host(session)
    visit_date, arrival = _near_future_schedule()
    with pytest.raises(VendorVisitError) as exc:
        create_vendor_visit(
            session, ctx,
            location_id=loc.id,
            visitor_type_code="CONTRACTOR",
            vendor_company_id=company.id,
            full_name="Worker",
            mobile="+91988111222",
            email="worker@test.com",
            host_id=host_id,
            work_purpose="Work",
            visit_date=visit_date,
            arrival_time=arrival,
            expected_duration_minutes=60,
            safety_acknowledged=True,
            po_work_order_reference="PO-1",
        )
    assert exc.value.code == "invalid_vendor"


def test_vendor_visit_missing_compliance_blocks_approval(test_db):
    TestingSessionLocal, _, session = test_db
    detail = _create_contractor_visit(session, "nocomp")
    visit_id = detail["id"]
    assert detail["compliance"]["compliance_status"] in (
        ComplianceStatus.NON_COMPLIANT.value,
        ComplianceStatus.REVIEW_REQUIRED.value,
    )
    owner = _owner_ctx(session)
    db = TestingSessionLocal()
    with pytest.raises(ApprovalError) as exc:
        approve_visit(db, owner, visit_id)
    assert "COMPLIANCE" in exc.value.code


def test_compliant_vendor_visit_can_be_approved(test_db):
    TestingSessionLocal, _, session = test_db
    detail = _create_contractor_visit(session, "compliant")
    visit_id = detail["id"]
    visit = session.get(Visit, visit_id)
    owner = _owner_ctx(session)
    _verify_all_mandatory(session, owner, visit_id, detail["vendor_company_id"], visit.visitor_id)
    evaluate_visit_compliance(session, visit_id, trigger="test")
    session.commit()
    session.refresh(visit)
    assert visit.compliance_status == ComplianceStatus.COMPLIANT.value
    db = TestingSessionLocal()
    approved = approve_visit(db, owner, visit_id)
    assert approved["status"] == VisitStatus.APPROVED.value


def test_expired_document_blocks_compliance(test_db):
    _, _, session = test_db
    detail = _create_contractor_visit(session, "expired")
    visit_id = detail["id"]
    visit = session.get(Visit, visit_id)
    owner = _owner_ctx(session)
    past = datetime.now(timezone.utc) - timedelta(days=5)
    doc = _upload_doc(
        session, owner, "INSURANCE_CERT",
        vendor_company_id=detail["vendor_company_id"],
        visit_id=visit_id,
        valid_until=past,
    )
    verify_document(session, owner, doc["id"], visit_id=visit_id)
    evaluation = evaluate_visit_compliance(session, visit_id, trigger="test")
    session.commit()
    assert evaluation.status == ComplianceStatus.NON_COMPLIANT.value
    assert visit.compliance_status == ComplianceStatus.NON_COMPLIANT.value


def test_document_expiring_before_visit_date_fails(test_db):
    _, _, session = test_db
    detail = _create_contractor_visit(session, "expvisit")
    visit_id = detail["id"]
    visit = _align_visit_schedule(session, visit_id, minutes_ahead=60 * 24 * 3)
    owner = _owner_ctx(session)
    expires_before_visit = visit.scheduled_start - timedelta(hours=1)
    doc = _upload_doc(
        session, owner, "INSURANCE_CERT",
        vendor_company_id=detail["vendor_company_id"],
        visit_id=visit_id,
        valid_until=expires_before_visit,
    )
    verify_document(session, owner, doc["id"], visit_id=visit_id)
    evaluation = evaluate_visit_compliance(session, visit_id, trigger="test")
    session.commit()
    assert evaluation.status == ComplianceStatus.NON_COMPLIANT.value


def _ensure_security_clear(session, visit_id: int):
    visit = session.get(Visit, visit_id)
    if visit.security_clearance_status == SecurityClearanceStatus.REVIEW.value:
        sec = _security_blr_ctx(session)
        resolve_clear(session, sec, visit_id, comment="cleared for test")
        session.commit()


def test_pending_verification_blocks_approval(test_db):
    TestingSessionLocal, _, session = test_db
    detail = _create_contractor_visit(session, "pending")
    visit_id = detail["id"]
    visit = session.get(Visit, visit_id)
    owner = _owner_ctx(session)
    for code in ("VENDOR_AUTH_LETTER", "INSURANCE_CERT", "SAFETY_TRAINING"):
        if code == "SAFETY_TRAINING":
            _upload_doc(session, owner, code, visitor_id=visit.visitor_id, visit_id=visit_id)
        else:
            _upload_doc(session, owner, code, vendor_company_id=detail["vendor_company_id"], visit_id=visit_id)
    evaluate_visit_compliance(session, visit_id, trigger="test")
    session.commit()
    visit = session.get(Visit, visit_id)
    assert visit.compliance_status == ComplianceStatus.REVIEW_REQUIRED.value
    db = TestingSessionLocal()
    try:
        with pytest.raises(ApprovalError) as exc:
            approve_visit(db, owner, visit_id)
        assert exc.value.code == "COMPLIANCE_REVIEW_REQUIRED"
    finally:
        _close_db(db)


def test_security_clear_does_not_bypass_compliance(test_db):
    TestingSessionLocal, _, session = test_db
    detail = _create_contractor_visit(session, "seccomb")
    visit_id = detail["id"]
    owner = _owner_ctx(session)
    sec = _security_blr_ctx(session)
    db = TestingSessionLocal()
    try:
        with pytest.raises(ApprovalError):
            approve_visit(db, owner, visit_id)
    finally:
        _close_db(db)
    visit = session.get(Visit, visit_id)
    visit.security_clearance_status = SecurityClearanceStatus.REVIEW.value
    session.commit()
    resolve_clear(session, sec, visit_id, comment="cleared")
    db2 = TestingSessionLocal()
    try:
        with pytest.raises(ApprovalError) as exc:
            approve_visit(db2, owner, visit_id)
        assert "COMPLIANCE" in exc.value.code
    finally:
        _close_db(db2)


def test_checkin_revalidates_expired_compliance(test_db):
    TestingSessionLocal, _, session = test_db
    detail = _create_contractor_visit(session, "checkinexp")
    visit_id = detail["id"]
    visit = _align_visit_schedule(session, visit_id)
    owner = _owner_ctx(session)
    sec = _security_blr_ctx(session)
    _verify_all_mandatory(session, owner, visit_id, detail["vendor_company_id"], visit.visitor_id)
    evaluate_visit_compliance(session, visit_id, trigger="test")
    session.commit()
    db = TestingSessionLocal()
    approve_visit(db, owner, visit_id)
    doc = session.query(ComplianceDocument).filter(
        ComplianceDocument.vendor_company_id == detail["vendor_company_id"],
        ComplianceDocument.requirement_id == _req_by_code(session, "INSURANCE_CERT").id,
    ).first()
    doc.valid_until = datetime.now(timezone.utc) - timedelta(days=1)
    doc.status = "EXPIRED"
    session.commit()
    db2 = TestingSessionLocal()
    mark_arrived(db2, sec, visit_id)
    with pytest.raises(OperationsError) as exc:
        check_in_visit(db2, sec, visit_id)
    assert "COMPLIANCE" in exc.value.code


def test_checkout_allowed_after_document_expires_onsite(test_db):
    TestingSessionLocal, _, session = test_db
    detail = _create_contractor_visit(session, "checkout")
    visit_id = detail["id"]
    visit = _align_visit_schedule(session, visit_id)
    owner = _owner_ctx(session)
    sec = _security_blr_ctx(session)
    _verify_all_mandatory(session, owner, visit_id, detail["vendor_company_id"], visit.visitor_id)
    evaluate_visit_compliance(session, visit_id, trigger="test")
    session.commit()
    db = TestingSessionLocal()
    approve_visit(db, owner, visit_id)
    mark_arrived(db, sec, visit_id)
    check_in_visit(db, sec, visit_id)
    doc = session.query(ComplianceDocument).filter(
        ComplianceDocument.vendor_company_id == detail["vendor_company_id"],
    ).first()
    doc.valid_until = datetime.now(timezone.utc) - timedelta(days=1)
    session.commit()
    check_out_visit(db, sec, visit_id)
    session.refresh(session.get(Visit, visit_id))
    assert session.get(Visit, visit_id).status == VisitStatus.CHECKED_OUT.value


def test_returning_contractor_reuses_valid_documents(test_db):
    TestingSessionLocal, _, session = test_db
    first = _create_contractor_visit(session, "reuse1", mobile="+91988123456", email="reuse@test.com", name="Reuse Kumar")
    visit_id = first["id"]
    visit = session.get(Visit, visit_id)
    owner = _owner_ctx(session)
    _verify_all_mandatory(session, owner, visit_id, first["vendor_company_id"], visit.visitor_id)
    evaluate_visit_compliance(session, visit_id, trigger="test")
    session.commit()
    second = _create_contractor_visit(
        session, "reuse2",
        vendor_company_id=first["vendor_company_id"],
        mobile="+91988123456",
        email="reuse@test.com",
        name="Reuse Kumar",
    )
    evaluation = evaluate_visit_compliance(session, second["id"], trigger="test")
    session.commit()
    assert evaluation.status == ComplianceStatus.COMPLIANT.value
    _ensure_security_clear(session, second["id"])
    db = TestingSessionLocal()
    try:
        approve_visit(db, owner, second["id"])
    finally:
        _close_db(db)
    session.refresh(session.get(Visit, second["id"]))
    assert session.get(Visit, second["id"]).status == VisitStatus.APPROVED.value


def test_full_returning_contractor_e2e(test_db):
    TestingSessionLocal, _, session = test_db
    owner = _owner_ctx(session)
    sec = _security_blr_ctx(session)
    company = _create_vendor_company(session, "E2E Vendor")
    vendor_id = company["id"]
    first = _create_contractor_visit(session, "e2e1", vendor_company_id=vendor_id, mobile="+91988222222", email="e2e@test.com")
    visit1 = session.get(Visit, first["id"])
    _verify_all_mandatory(session, owner, first["id"], vendor_id, visit1.visitor_id)
    evaluate_visit_compliance(session, first["id"], trigger="test")
    session.commit()
    db = TestingSessionLocal()
    try:
        _align_visit_schedule(session, first["id"])
        approve_visit(db, owner, first["id"])
    finally:
        _close_db(db)
    visit = session.get(Visit, first["id"])
    session.refresh(visit)
    assert visit.invitation_token
    sec_db = TestingSessionLocal()
    try:
        verify_by_token(sec_db, sec, visit.invitation_token)
        mark_arrived(sec_db, sec, first["id"])
        check_in_visit(sec_db, sec, first["id"])
        check_out_visit(sec_db, sec, first["id"])
    finally:
        _close_db(sec_db)

    second = _create_contractor_visit(
        session, "e2e2", vendor_company_id=vendor_id,
        mobile="+91988222222", email="e2e@test.com", name=visit1.visitor.full_name,
    )
    evaluate_visit_compliance(session, second["id"], trigger="test")
    session.commit()
    _ensure_security_clear(session, second["id"])
    db2 = TestingSessionLocal()
    try:
        _align_visit_schedule(session, second["id"])
        approve_visit(db2, owner, second["id"])
    finally:
        _close_db(db2)
    visit2 = session.get(Visit, second["id"])
    session.refresh(visit2)
    sec_db2 = TestingSessionLocal()
    try:
        verify_by_token(sec_db2, sec, visit2.invitation_token)
        mark_arrived(sec_db2, sec, second["id"])
        resolve_clear(sec_db2, sec, second["id"], comment="clear for checkin")
        check_in_visit(sec_db2, sec, second["id"])
    finally:
        _close_db(sec_db2)
    session.expire_all()
    assert session.get(Visit, second["id"]).status == VisitStatus.ONSITE.value


def test_expired_document_renewal_e2e(test_db):
    TestingSessionLocal, _, session = test_db
    owner = _owner_ctx(session)
    detail = _create_contractor_visit(session, "renew")
    visit_id = detail["id"]
    visit = session.get(Visit, visit_id)
    past = datetime.now(timezone.utc) - timedelta(days=2)
    doc = _upload_doc(session, owner, "INSURANCE_CERT", vendor_company_id=detail["vendor_company_id"], visit_id=visit_id, valid_until=past)
    verify_document(session, owner, doc["id"], visit_id=visit_id)
    evaluate_visit_compliance(session, visit_id, trigger="test")
    session.commit()
    db = TestingSessionLocal()
    try:
        with pytest.raises(ApprovalError):
            approve_visit(db, owner, visit_id)
    finally:
        _close_db(db)
    new_doc = _upload_doc(
        session, owner, "INSURANCE_CERT",
        vendor_company_id=detail["vendor_company_id"],
        visit_id=visit_id,
        valid_until=datetime.now(timezone.utc) + timedelta(days=60),
    )
    verify_document(session, owner, new_doc["id"], visit_id=visit_id)
    for code in ("VENDOR_AUTH_LETTER", "SAFETY_TRAINING"):
        if code == "SAFETY_TRAINING":
            d = _upload_doc(session, owner, code, visitor_id=visit.visitor_id, visit_id=visit_id)
        else:
            d = _upload_doc(session, owner, code, vendor_company_id=detail["vendor_company_id"], visit_id=visit_id)
        verify_document(session, owner, d["id"], visit_id=visit_id)
    evaluate_visit_compliance(session, visit_id, trigger="test")
    session.commit()
    db2 = TestingSessionLocal()
    try:
        approve_visit(db2, owner, visit_id)
    finally:
        _close_db(db2)
    assert session.get(Visit, visit_id).status == VisitStatus.APPROVED.value


def test_site_admin_blr_cannot_see_mumbai_compliance(client):
    c, TestingSessionLocal, session = client
    owner = _owner_ctx(session)
    mum_host_id, mum = _mum_host(session)
    company = create_vendor_company(session, owner, name="Mumbai Vendor", location_ids=[mum.id])
    visit_date, arrival = _near_future_schedule()
    create_vendor_visit(
        session, owner,
        location_id=mum.id,
        visitor_type_code="CONTRACTOR",
        vendor_company_id=company["id"],
        full_name="Mumbai Worker",
        mobile="+91988333333",
        email="mumworker@test.com",
        host_id=mum_host_id,
        work_purpose="Work",
        visit_date=visit_date,
        arrival_time=arrival,
        expected_duration_minutes=60,
        safety_acknowledged=True,
        po_work_order_reference="PO-MUM",
    )
    r = c.get("/api/compliance/reviews", headers={"X-Dev-User-Email": "siteadmin.blr@vms.local"})
    assert r.status_code == 200
    ids = [item["visit_id"] for item in r.json()["items"]]
    mum_visit = session.query(Visit).filter(Visit.location_id == mum.id).order_by(Visit.id.desc()).first()
    assert mum_visit.id not in ids


def test_file_security_rejects_bad_extension():
    with pytest.raises(DocumentStorageError):
        validate_upload("malware.exe", "application/octet-stream", 100)


def test_file_security_rejects_path_traversal_name():
    with pytest.raises(DocumentStorageError):
        validate_upload("../../evil.pdf", "application/pdf", 100)


def test_unauthorized_download_blocked(client):
    c, TestingSessionLocal, session = client
    owner = _owner_ctx(session)
    detail = _create_contractor_visit(session, "dl")
    visit_id = detail["id"]
    doc = _upload_doc(session, owner, "INSURANCE_CERT", vendor_company_id=detail["vendor_company_id"], visit_id=visit_id)
    r = c.get(f"/api/compliance-documents/{doc['id']}/download", headers={"X-Dev-User-Email": "security.blr@vms.local"})
    assert r.status_code == 403


def test_walk_in_contractor_requires_compliance_followup(test_db):
    TestingSessionLocal, _, session = test_db
    host_id, loc = _blr_host(session)
    result = create_self_registration(
        session,
        site_token=loc.public_registration_token,
        visitor_type_code="CONTRACTOR",
        full_name="Walkin Contractor",
        mobile="+91988444444",
        email="walkin@test.com",
        company="Walk Co",
        host_id=host_id,
        purpose="Repair",
        expected_duration_minutes=60,
        policy_accepted=True,
    )
    visit = session.query(Visit).filter(Visit.registration_reference == result["registration_reference"]).first()
    assert visit.compliance_status in (
        ComplianceStatus.NON_COMPLIANT.value,
        ComplianceStatus.REVIEW_REQUIRED.value,
    )
    owner = _owner_ctx(session)
    company = _create_vendor_company(session, "Walk Vendor")
    loc = session.query(Location).filter(Location.code == "BLR").first()
    from app.domain.models import VendorCompanyLocation
    session.add(VendorCompanyLocation(vendor_company_id=company["id"], location_id=loc.id, is_active=True))
    session.add(
        VendorVisitDetails(
            visit_id=visit.id,
            vendor_company_id=company["id"],
            work_purpose="Repair",
            po_work_order_reference="PO-WALK",
            company_contact_host_id=host_id,
            safety_acknowledged=True,
            safety_acknowledged_at=datetime.now(timezone.utc),
            safety_policy_version="v1",
        )
    )
    session.commit()
    _verify_all_mandatory(session, owner, visit.id, company["id"], visit.visitor_id)
    evaluate_visit_compliance(session, visit.id, trigger="test")
    session.commit()
    assert visit.compliance_status == ComplianceStatus.COMPLIANT.value
    _ensure_security_clear(session, visit.id)
    db = TestingSessionLocal()
    try:
        approve_visit(db, owner, visit.id)
    finally:
        _close_db(db)
    session.refresh(visit)
    assert visit.status == VisitStatus.APPROVED.value


def test_vendor_companies_api(client):
    c, _, session = client
    owner = _owner_ctx(session)
    loc = session.query(Location).filter(Location.code == "BLR").first()
    create_vendor_company(session, owner, name="API Vendor", location_ids=[loc.id])
    r = c.get("/api/vendor-companies", headers={"X-Dev-User-Email": "sheru.bohra@lazypay.in"})
    assert r.status_code == 200
    assert r.json()["total"] >= 1


def test_security_cannot_create_vendor_via_api(client):
    c, _, session = client
    loc = session.query(Location).filter(Location.code == "BLR").first()
    r = c.post(
        "/api/vendor-companies",
        headers={"X-Dev-User-Email": "security.blr@vms.local"},
        json={"name": "Sec Vendor", "location_ids": [loc.id]},
    )
    assert r.status_code == 403
