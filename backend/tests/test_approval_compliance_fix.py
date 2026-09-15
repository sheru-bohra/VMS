"""Approval compliance gate regression tests after free-text vendor company change."""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.application.approval_service import ApprovalError, approve_visit
from app.application.auth_service import build_auth_context
from app.application.bootstrap import bootstrap_development_data
from app.application.compliance_document_service import upload_document, verify_document
from app.application.compliance_service import ComplianceError, ensure_allows_approval, evaluate_visit_compliance
from app.application.invitation_service import create_advance_visit, InvitationError
from app.application.security_review_service import resolve_clear
from app.application.security_screening_service import screen_visit
from app.domain.enums import ComplianceStatus, SecurityClearanceStatus, VisitSource, VisitStatus
from app.domain.models import AdminUser, Host, HostLocationAssignment, Location, Visit, VisitorType
from tests.test_phase8 import (
    PDF_BYTES,
    _align_visit_schedule,
    _blr_host,
    _create_contractor_visit,
    _create_vendor_company,
    _ensure_security_clear,
    _near_future_schedule,
    _owner_ctx,
    _upload_doc,
    _verify_all_mandatory,
)


@pytest.fixture
def test_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    from app.infrastructure.database import Base

    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    bootstrap_development_data(db)
    db.commit()
    yield TestingSessionLocal, engine, db
    db.close()
    os.unlink(path)


def _register_advance(
    session,
    *,
    visitor_type_code: str,
    company: str,
    full_name: str,
    mobile: str = "9881111001",
    email: str = "visitor@example.invalid",
    po: str = "PO-TEST-1",
    safety: bool = True,
    govt_id_type: str = "PASSPORT",
    govt_id_number: str = "P1234567",
    signature_storage_key: str = "sig-key",
    work_purpose: str = "Maintenance",
    purpose: str = "Maintenance",
):
    owner = _owner_ctx(session)
    host_id, loc = _blr_host(session)
    visit_date, arrival = _near_future_schedule()
    return create_advance_visit(
        session,
        owner,
        location_id=loc.id,
        visitor_type_code=visitor_type_code,
        full_name=full_name,
        mobile=mobile,
        email=email,
        company=company,
        host_id=host_id,
        visit_date=visit_date,
        arrival_time=arrival,
        expected_duration_minutes=120,
        purpose=purpose,
        govt_id_type=govt_id_type,
        govt_id_number=govt_id_number,
        signature_storage_key=signature_storage_key,
        work_purpose=work_purpose,
        po_work_order_reference=po,
        safety_acknowledged=safety,
        safety_induction_completed=safety,
    )


def test_free_text_vendor_without_vendor_master_can_be_approved(test_db):
    TestingSessionLocal, _, session = test_db
    detail = _register_advance(
        session,
        visitor_type_code="VENDOR",
        company="UNREGISTERED MOCK COMPANY",
        full_name="Free Text Vendor",
        mobile="9881111011",
    )
    visit_id = detail["id"]
    visit = session.get(Visit, visit_id)
    assert visit is not None
    assert visit.compliance_status in (None, ComplianceStatus.COMPLIANT.value)

    evaluate_visit_compliance(session, visit_id, trigger="test")
    session.commit()
    session.refresh(visit)
    assert visit.compliance_status == ComplianceStatus.COMPLIANT.value

    _ensure_security_clear(session, visit_id)
    db = TestingSessionLocal()
    approved = approve_visit(db, _owner_ctx(session), visit_id)
    assert approved["status"] == VisitStatus.APPROVED.value


def test_business_visitor_can_be_approved(test_db):
    TestingSessionLocal, _, session = test_db
    detail = _register_advance(
        session,
        visitor_type_code="BUSINESS",
        company="Acme Corp",
        full_name="Business Visitor",
        mobile="9881111012",
        po="",
        safety=False,
        govt_id_type="",
        govt_id_number="",
        signature_storage_key="",
        work_purpose="",
        purpose="Business meeting",
    )
    visit_id = detail["id"]
    _ensure_security_clear(session, visit_id)
    db = TestingSessionLocal()
    approved = approve_visit(db, _owner_ctx(session), visit_id)
    assert approved["status"] == VisitStatus.APPROVED.value


def test_partner_vip_candidate_delivery_types_can_be_approved(test_db):
    TestingSessionLocal, _, session = test_db
    owner = _owner_ctx(session)
    mobiles = ["9881111021", "9881111022", "9881111023", "9881111024", "9881111025"]
    for idx, (code, name) in enumerate((
        ("PARTNER", "Partner Visitor"),
        ("VIP", "VIP Visitor"),
        ("INTERVIEW", "Candidate Visitor"),
        ("DELIVERY", "Delivery Visitor"),
        ("SERVICE", "Service Visitor"),
    )):
        detail = _register_advance(
            session,
            visitor_type_code=code,
            company="Test Co" if code != "DELIVERY" else "",
            full_name=name,
            mobile=mobiles[idx],
            email=f"{code.lower()}@example.invalid",
            po="PO-SVC-1" if code in ("CONTRACTOR", "SERVICE", "VENDOR") else "PO-1",
            safety=code in ("VENDOR", "CONTRACTOR", "SERVICE"),
            govt_id_type="PASSPORT" if code in ("VENDOR", "CONTRACTOR", "SERVICE") else "",
            govt_id_number="P999" if code in ("VENDOR", "CONTRACTOR", "SERVICE") else "",
            signature_storage_key="sig" if code in ("VENDOR", "CONTRACTOR", "SERVICE") else "",
            work_purpose="Work" if code in ("VENDOR", "CONTRACTOR", "SERVICE") else "",
            purpose="Meeting" if code in ("PARTNER", "VIP", "INTERVIEW", "DELIVERY", "EVENT", "OTHER") else "Maintenance",
        )
        _ensure_security_clear(session, detail["id"])
        db = TestingSessionLocal()
        approved = approve_visit(db, owner, detail["id"])
        assert approved["status"] == VisitStatus.APPROVED.value


def test_linked_vendor_with_verified_documents_can_be_approved(test_db):
    TestingSessionLocal, _, session = test_db
    detail = _create_contractor_visit(session, "linked-vendor")
    visit_id = detail["id"]
    visit = session.get(Visit, visit_id)
    owner = _owner_ctx(session)
    _verify_all_mandatory(session, owner, visit_id, detail["vendor_company_id"], visit.visitor_id)
    evaluate_visit_compliance(session, visit_id, trigger="test")
    session.commit()
    _ensure_security_clear(session, visit_id)
    db = TestingSessionLocal()
    approved = approve_visit(db, owner, visit_id)
    assert approved["status"] == VisitStatus.APPROVED.value


def test_linked_vendor_missing_mandatory_document_blocks_approval(test_db):
    TestingSessionLocal, _, session = test_db
    detail = _create_contractor_visit(session, "missing-doc")
    visit_id = detail["id"]
    evaluate_visit_compliance(session, visit_id, trigger="test")
    session.commit()
    _ensure_security_clear(session, visit_id)
    db = TestingSessionLocal()
    with pytest.raises(ApprovalError) as exc:
        approve_visit(db, _owner_ctx(session), visit_id)
    assert exc.value.code == "COMPLIANCE_NON_COMPLIANT"
    assert "Approval blocked" in exc.value.message


def test_expired_contractor_document_blocks_approval(test_db):
    TestingSessionLocal, _, session = test_db
    detail = _create_contractor_visit(session, "expired-contractor")
    visit_id = detail["id"]
    visit = session.get(Visit, visit_id)
    owner = _owner_ctx(session)
    past = datetime.now(timezone.utc) - timedelta(days=5)
    doc = _upload_doc(
        session,
        owner,
        "INSURANCE_CERT",
        vendor_company_id=detail["vendor_company_id"],
        visit_id=visit_id,
        valid_until=past,
    )
    verify_document(session, owner, doc["id"], visit_id=visit_id)
    for code in ("VENDOR_AUTH_LETTER", "SAFETY_TRAINING"):
        if code == "SAFETY_TRAINING":
            extra = _upload_doc(session, owner, code, visitor_id=visit.visitor_id, visit_id=visit_id)
        else:
            extra = _upload_doc(session, owner, code, vendor_company_id=detail["vendor_company_id"], visit_id=visit_id)
        verify_document(session, owner, extra["id"], visit_id=visit_id)
    evaluate_visit_compliance(session, visit_id, trigger="test")
    session.commit()
    _ensure_security_clear(session, visit_id)
    db = TestingSessionLocal()
    with pytest.raises(ApprovalError) as exc:
        approve_visit(db, owner, visit_id)
    assert exc.value.code == "COMPLIANCE_NON_COMPLIANT"
    assert "expired" in exc.value.message.lower()


def test_security_blocked_still_blocks_approval(test_db):
    TestingSessionLocal, _, session = test_db
    detail = _register_advance(
        session,
        visitor_type_code="BUSINESS",
        company="Secure Co",
        full_name="Blocked Visitor",
        mobile="9881111018",
        po="",
        safety=False,
        govt_id_type="",
        govt_id_number="",
        signature_storage_key="",
        work_purpose="",
        purpose="Security review meeting",
    )
    visit = session.get(Visit, detail["id"])
    visit.security_clearance_status = SecurityClearanceStatus.BLOCKED.value
    session.commit()
    session.refresh(visit)
    assert visit.security_clearance_status == SecurityClearanceStatus.BLOCKED.value
    db = TestingSessionLocal()
    with pytest.raises(ApprovalError):
        approve_visit(db, _owner_ctx(session), detail["id"])


def test_policy_not_accepted_blocks_registration(test_db):
    _, _, session = test_db
    owner = _owner_ctx(session)
    host_id, loc = _blr_host(session)
    visit_date, arrival = _near_future_schedule()
    with pytest.raises(InvitationError):
        create_advance_visit(
            session,
            owner,
            location_id=loc.id,
            visitor_type_code="BUSINESS",
            full_name="No Policy",
            mobile="+91988111019",
            email="policy@example.invalid",
            company="Policy Co",
            host_id=host_id,
            visit_date=visit_date,
            arrival_time=arrival,
            expected_duration_minutes=60,
            purpose="Meeting",
            policy_accepted=False,
        )


def test_ensure_allows_approval_returns_specific_message(test_db):
    _, _, session = test_db
    detail = _create_contractor_visit(session, "message-test")
    visit_id = detail["id"]
    evaluate_visit_compliance(session, visit_id, trigger="test")
    session.commit()
    with pytest.raises(ComplianceError) as exc:
        ensure_allows_approval(session, visit_id)
    assert exc.value.code == "COMPLIANCE_NON_COMPLIANT"
    assert "Approval blocked" in exc.value.message
