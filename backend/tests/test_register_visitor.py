"""Register visitor extended registration flow."""

import os
import tempfile
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.application.bootstrap import bootstrap_development_data
from app.application.invitation_service import create_advance_visit, InvitationError, validate_indian_mobile
from app.application.register_visitor_policy import get_register_visitor_policy
from app.application.vendor_company_service import create_vendor_company
from app.domain.enums import VisitStatus
from app.application.auth_service import build_auth_context
from app.domain.models import (
    AdminUser,
    Host,
    HostLocationAssignment,
    Location,
    VendorCompanyLocation,
    Visit,
    VisitorType,
)
from app.infrastructure.database import Base


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


def _blr_host_id(session):
    loc = session.query(Location).filter(Location.code == "BLR").first()
    ha = session.query(HostLocationAssignment).filter(HostLocationAssignment.location_id == loc.id).first()
    return ha.host_id, loc.id


def _owner_ctx(session):
    user = session.query(AdminUser).filter(AdminUser.email == "sheru.bohra@lazypay.in").first()
    return build_auth_context(user)


def _future_visit_date():
    return (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")


def test_register_visitor_policy_required(test_db):
    _, _, session = test_db
    host_id, loc_id = _blr_host_id(session)
    ctx = _owner_ctx(session)
    with pytest.raises(InvitationError) as exc:
        create_advance_visit(
            session,
            ctx,
            location_id=loc_id,
            visitor_type_code="BUSINESS",
            full_name="Policy Test",
            mobile="9881112223",
            email="policy@test.com",
            company="Co",
            host_id=host_id,
            visit_date=_future_visit_date(),
            arrival_time="10:00",
            expected_duration_minutes=60,
            purpose="Meeting",
            policy_accepted=False,
            departure_time="11:00",
        )
    assert exc.value.code == "policy_required"


def test_register_visitor_business_without_govt_id(test_db):
    _, _, session = test_db
    host_id, loc_id = _blr_host_id(session)
    ctx = _owner_ctx(session)
    result = create_advance_visit(
        session,
        ctx,
        location_id=loc_id,
        visitor_type_code="BUSINESS",
        full_name="Business Visitor",
        mobile="9881112224",
        email="business@test.com",
        company="Business Co",
        host_id=host_id,
        visit_date=_future_visit_date(),
        arrival_time="10:00",
        expected_duration_minutes=60,
        purpose="Meeting",
        policy_accepted=True,
        departure_time="11:00",
    )
    assert result["status"] == VisitStatus.PENDING_APPROVAL.value
    visit = session.get(Visit, result["id"])
    assert visit.created_by_user_id == ctx.user_id


def test_register_visitor_vip_without_company_or_govt_id(test_db):
    _, _, session = test_db
    host_id, loc_id = _blr_host_id(session)
    ctx = _owner_ctx(session)
    result = create_advance_visit(
        session,
        ctx,
        location_id=loc_id,
        visitor_type_code="VIP",
        full_name="VIP Guest",
        mobile="9881112225",
        email=None,
        company=None,
        host_id=host_id,
        visit_date=_future_visit_date(),
        arrival_time="10:00",
        expected_duration_minutes=60,
        purpose="Executive visit",
        policy_accepted=True,
        departure_time="11:00",
    )
    assert result["status"] == VisitStatus.PENDING_APPROVAL.value


def test_register_visitor_mobile_validation(test_db):
    _, _, session = test_db
    host_id, loc_id = _blr_host_id(session)
    ctx = _owner_ctx(session)
    with pytest.raises(InvitationError) as exc:
        create_advance_visit(
            session,
            ctx,
            location_id=loc_id,
            visitor_type_code="BUSINESS",
            full_name="Mobile Test",
            mobile="98811122",
            email="m@test.com",
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

    with pytest.raises(InvitationError):
        validate_indian_mobile("98ABC43210")


def test_register_visitor_vendor_requires_govt_id(test_db):
    _, _, session = test_db
    host_id, loc_id = _blr_host_id(session)
    ctx = _owner_ctx(session)
    with pytest.raises(InvitationError) as exc:
        create_advance_visit(
            session,
            ctx,
            location_id=loc_id,
            visitor_type_code="VENDOR",
            full_name="Vendor Test",
            mobile="9881112226",
            email="vendor@test.com",
            company="Missing Vendor Co",
            host_id=host_id,
            visit_date=_future_visit_date(),
            arrival_time="10:00",
            expected_duration_minutes=60,
            purpose="Work",
            policy_accepted=True,
            departure_time="12:00",
            work_purpose="Install",
            po_work_order_reference="PO-1",
            safety_acknowledged=True,
        )
    assert exc.value.code in ("govt_id_required", "signature_required")


def test_register_visitor_vendor_unknown_company_accepted(test_db):
    _, _, session = test_db
    host_id, loc_id = _blr_host_id(session)
    ctx = _owner_ctx(session)
    result = create_advance_visit(
        session,
        ctx,
        location_id=loc_id,
        visitor_type_code="VENDOR",
        full_name="Vendor Free Text",
        mobile="9881112240",
        email="vendor-free@test.com",
        company="test",
        host_id=host_id,
        visit_date=_future_visit_date(),
        arrival_time="10:00",
        expected_duration_minutes=60,
        purpose="Work",
        policy_accepted=True,
        departure_time="12:00",
        work_purpose="Install",
        po_work_order_reference="PO-1",
        safety_acknowledged=True,
        govt_id_type="PASSPORT",
        govt_id_number="AB1234567",
        signature_storage_key="sig-key",
    )
    assert result["status"] == VisitStatus.PENDING_APPROVAL.value
    visit = session.get(Visit, result["id"])
    assert visit.visitor.company == "test"
    assert visit.vendor_visit_details is None


def test_register_visitor_vendor_blank_company_rejected(test_db):
    _, _, session = test_db
    host_id, loc_id = _blr_host_id(session)
    ctx = _owner_ctx(session)
    with pytest.raises(InvitationError) as exc:
        create_advance_visit(
            session,
            ctx,
            location_id=loc_id,
            visitor_type_code="VENDOR",
            full_name="Vendor Blank Co",
            mobile="9881112241",
            email="vendor-blank@test.com",
            company="   ",
            host_id=host_id,
            visit_date=_future_visit_date(),
            arrival_time="10:00",
            expected_duration_minutes=60,
            purpose="Work",
            policy_accepted=True,
            departure_time="12:00",
            work_purpose="Install",
            po_work_order_reference="PO-1",
            safety_acknowledged=True,
            govt_id_type="PASSPORT",
            govt_id_number="AB1234567",
            signature_storage_key="sig-key",
        )
    assert exc.value.code == "company_required"


def test_register_visitor_registered_by_from_auth_context(test_db):
    _, _, session = test_db
    host_id, loc_id = _blr_host_id(session)
    ctx = _owner_ctx(session)
    result = create_advance_visit(
        session,
        ctx,
        location_id=loc_id,
        visitor_type_code="PARTNER",
        full_name="Partner Visitor",
        mobile="9881112227",
        email="partner@test.com",
        company="Partner Co",
        host_id=host_id,
        visit_date=_future_visit_date(),
        arrival_time="10:00",
        expected_duration_minutes=60,
        purpose="Partnership review",
        policy_accepted=True,
        departure_time="11:30",
    )
    visit = session.get(Visit, result["id"])
    creator = session.get(AdminUser, visit.created_by_user_id)
    assert creator.email == ctx.email
    assert creator.display_name


def test_register_visitor_extended_metadata(test_db):
    _, _, session = test_db
    host_id, loc_id = _blr_host_id(session)
    ctx = _owner_ctx(session)
    result = create_advance_visit(
        session,
        ctx,
        location_id=loc_id,
        visitor_type_code="BUSINESS",
        full_name="Extended Visitor",
        mobile="9881112228",
        email="extended@test.com",
        company="Extended Co",
        host_id=host_id,
        visit_date=_future_visit_date(),
        arrival_time="10:00",
        expected_duration_minutes=60,
        purpose="Meeting",
        policy_accepted=True,
        address="123 Test Street",
        vehicle_number="AB12CD",
        vehicle_type="CAR",
        assets=["laptop", "mobile"],
        govt_id_type="PASSPORT",
        govt_id_number="X1234567",
        nda_signed=True,
        departure_time="11:00",
    )
    assert result["status"] == VisitStatus.PENDING_APPROVAL.value
    visit = session.get(Visit, result["id"])
    assert visit is not None
    meta = visit.registration_metadata_json or {}
    assert meta.get("vehicle_number") == "AB12CD"
    assert visit.visitor.address == "123 Test Street"


def test_register_visitor_departure_time(test_db):
    _, _, session = test_db
    host_id, loc_id = _blr_host_id(session)
    ctx = _owner_ctx(session)
    result = create_advance_visit(
        session,
        ctx,
        location_id=loc_id,
        visitor_type_code="BUSINESS",
        full_name="Departure Visitor",
        mobile="9881112229",
        email="departure@test.com",
        company="Co",
        host_id=host_id,
        visit_date=_future_visit_date(),
        arrival_time="10:00",
        expected_duration_minutes=60,
        purpose="Meeting",
        policy_accepted=True,
        departure_time="12:00",
    )
    visit = session.get(Visit, result["id"])
    assert visit.expected_duration_minutes == 120


def test_register_visitor_delivery_without_host(test_db):
    _, _, session = test_db
    _, loc_id = _blr_host_id(session)
    ctx = _owner_ctx(session)
    policy = get_register_visitor_policy(
        session.query(VisitorType).filter(VisitorType.code == "DELIVERY").first()
    )
    assert policy.host_required is False
    result = create_advance_visit(
        session,
        ctx,
        location_id=loc_id,
        visitor_type_code="DELIVERY",
        full_name="Courier",
        mobile="9881112230",
        email=None,
        company="Fast Courier",
        host_id=None,
        visit_date=_future_visit_date(),
        arrival_time="10:00",
        expected_duration_minutes=30,
        purpose="Delivery",
        policy_accepted=True,
        departure_time="10:30",
    )
    visit = session.get(Visit, result["id"])
    assert visit.host_id is None


def test_register_visitor_vendor_with_company_match(test_db):
    _, _, session = test_db
    host_id, loc_id = _blr_host_id(session)
    ctx = _owner_ctx(session)
    company = create_vendor_company(
        session,
        ctx,
        name="Matched Vendor Ltd",
        location_ids=[loc_id],
    )
    session.add(
        VendorCompanyLocation(
            vendor_company_id=company["id"],
            location_id=loc_id,
            is_active=True,
        )
    )
    session.commit()
    result = create_advance_visit(
        session,
        ctx,
        location_id=loc_id,
        visitor_type_code="VENDOR",
        full_name="Vendor Worker",
        mobile="9881112231",
        email="worker@vendor.com",
        company="Matched Vendor Ltd",
        host_id=host_id,
        visit_date=_future_visit_date(),
        arrival_time="10:00",
        expected_duration_minutes=60,
        purpose="Maintenance",
        policy_accepted=True,
        departure_time="12:00",
        work_purpose="Equipment repair",
        po_work_order_reference="PO-99",
        safety_acknowledged=True,
        govt_id_type="PASSPORT",
        govt_id_number="AB1234567",
        signature_storage_key="sig-key",
    )
    assert result["status"] == VisitStatus.PENDING_APPROVAL.value
    visit = session.get(Visit, result["id"])
    assert visit.vendor_visit_details is not None
    assert visit.vendor_visit_details.vendor_company_id == company["id"]
