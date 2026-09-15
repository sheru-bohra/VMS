import os
import tempfile
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.application.approval_service import approve_visit, reject_visit
from app.application.auth_service import build_auth_context
from app.application.bootstrap import bootstrap_development_data
from app.application.badge_service import BadgeError, issue_badge, record_print
from app.application.invitation_service import (
    InvitationError,
    cancel_invitation,
    create_advance_visit,
    get_public_invitation,
)
from app.application.operations_service import check_in_visit, check_out_visit, mark_arrived
from app.application.visitor_qr_service import QrVerifyError, verify_by_token
from app.core.config import settings
from app.domain.enums import BadgeStatus, AdminRole, Permission, VisitSource, VisitStatus, get_permissions_for_role
from app.domain.models import AdminUser, Host, HostLocationAssignment, Location, Visit, VisitorBadge
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


def _security_blr_ctx(session):
    user = session.query(AdminUser).filter(AdminUser.email == "security.blr@vms.local").first()
    return build_auth_context(user)


def _blr_host_id(session):
    loc = session.query(Location).filter(Location.code == "BLR").first()
    ha = session.query(HostLocationAssignment).filter(HostLocationAssignment.location_id == loc.id).first()
    return ha.host_id, loc.id


def _site_admin_blr_ctx(session):
    user = session.query(AdminUser).filter(AdminUser.email == "siteadmin.blr@vms.local").first()
    return build_auth_context(user)


def _near_future_schedule():
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")
    return tomorrow, "10:30"


def _align_visit_schedule(session, visit_id: int) -> Visit:
    visit = session.get(Visit, visit_id)
    now = datetime.now(timezone.utc)
    visit.scheduled_start = now + timedelta(minutes=30)
    visit.scheduled_end = visit.scheduled_start + timedelta(minutes=60)
    session.commit()
    session.refresh(visit)
    return visit


def _create_advance(session, suffix="1", location_id=None, ctx=None):
    ctx = ctx or _owner_ctx(session)
    host_id, loc_id = _blr_host_id(session)
    if location_id is not None:
        loc_id = location_id
    visit_date, arrival = _near_future_schedule()
    return create_advance_visit(
        db=session,
        ctx=ctx,
        location_id=loc_id,
        visitor_type_code="BUSINESS",
        full_name=f"Advance Visitor {suffix}",
        mobile=f"98765{abs(hash(suffix)) % 100000:05d}",
        email=f"adv{suffix}@test.com",
        company="Adv Co",
        host_id=host_id,
        visit_date=visit_date,
        arrival_time=arrival,
        expected_duration_minutes=60,
        purpose="Scheduled meeting",
    )


def test_advance_visit_pending_approval(test_db):
    _, _, session = test_db
    result = _create_advance(session, "pending")
    assert result["status"] == VisitStatus.PENDING_APPROVAL.value
    assert result["source"] == VisitSource.ADVANCE_REGISTRATION.value
    assert result["registration_reference"].startswith("VMS-")


def test_security_cannot_create_advance(client):
    c, _, session = client
    host_id, loc_id = _blr_host_id(session)
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")
    r = c.post(
        "/api/invitations",
        headers={"X-Dev-User-Email": "security.blr@vms.local"},
        json={
            "location_id": loc_id,
            "visitor_type": "BUSINESS",
            "full_name": "Blocked",
            "mobile": "9990000000",
            "email": "blocked@test.com",
            "company": "Co",
            "host_id": host_id,
            "visit_date": tomorrow,
            "arrival_time": "11:00",
            "expected_duration_minutes": 60,
            "purpose": "Test",
        },
    )
    assert r.status_code == 403


def test_approval_activates_invitation(test_db):
    TestingSessionLocal, _, session = test_db
    detail = _create_advance(session, "approve")
    visit_id = detail["id"]
    ctx = _owner_ctx(session)
    db = TestingSessionLocal()
    approve_visit(db, ctx, visit_id)
    visit = session.get(__import__("app.domain.models", fromlist=["Visit"]).Visit, visit_id)
    assert visit.invitation_active is True
    assert visit.invitation_token is not None


def test_qr_verify_cross_location_blocked(test_db):
    TestingSessionLocal, _, session = test_db
    from app.domain.models import Visit
    detail = _create_advance(session, "cross")
    visit_id = detail["id"]
    visit = session.get(Visit, visit_id)
    now = datetime.now(timezone.utc)
    visit.scheduled_start = now + timedelta(minutes=30)
    visit.scheduled_end = visit.scheduled_start + timedelta(minutes=60)
    session.commit()
    ctx = _owner_ctx(session)
    db = TestingSessionLocal()
    approve_visit(db, ctx, visit_id)
    visit = session.get(Visit, visit_id)
    sec_ctx = _security_blr_ctx(session)
    db2 = TestingSessionLocal()
    result = verify_by_token(db2, sec_ctx, visit.invitation_token)
    assert result["valid"] is True

    mum = session.query(Location).filter(Location.code == "MUM").first()
    visit.location_id = mum.id
    session.commit()
    from app.application.visitor_qr_service import QrVerifyError
    with pytest.raises(QrVerifyError) as exc:
        verify_by_token(db2, sec_ctx, visit.invitation_token)
    assert exc.value.status_code == 403


def test_badge_issue_onsite_only(test_db):
    TestingSessionLocal, _, session = test_db
    detail = _create_advance(session, "badge")
    visit_id = detail["id"]
    ctx = _owner_ctx(session)
    db = TestingSessionLocal()
    from app.application.badge_service import BadgeError
    with pytest.raises(BadgeError):
        issue_badge(db, ctx, visit_id)


def test_security_role_no_invitation_create():
    from app.domain.enums import AdminRole, Permission, get_permissions_for_role
    perms = get_permissions_for_role(AdminRole.SECURITY)
    assert Permission.INVITATION_CREATE not in perms
    assert Permission.VISITOR_QR_VERIFY in perms
    assert Permission.BADGE_ISSUE in perms


def test_public_invitation_after_approval(test_db):
    TestingSessionLocal, _, session = test_db
    detail = _create_advance(session, "public")
    visit_id = detail["id"]
    _align_visit_schedule(session, visit_id)
    ctx = _owner_ctx(session)
    db = TestingSessionLocal()
    approve_visit(db, ctx, visit_id)
    visit = session.get(Visit, visit_id)
    data = get_public_invitation(db, visit.invitation_token)
    assert data["visitor_name"].startswith("Advance Visitor")


def test_site_admin_blr_cannot_create_mumbai_visit(client):
    c, _, session = client
    mum = session.query(Location).filter(Location.code == "MUM").first()
    host_id, _ = _blr_host_id(session)
    visit_date, arrival = _near_future_schedule()
    r = c.post(
        "/api/invitations",
        headers={"X-Dev-User-Email": "siteadmin.blr@vms.local"},
        json={
            "location_id": mum.id,
            "visitor_type": "BUSINESS",
            "full_name": "Mumbai Blocked",
            "mobile": "9990088770",
            "email": "mumblock@test.com",
            "company": "Co",
            "host_id": host_id,
            "visit_date": visit_date,
            "arrival_time": arrival,
            "expected_duration_minutes": 60,
            "purpose": "Test",
        },
    )
    assert r.status_code == 403


def test_cancelled_invitation_invalidates_qr(test_db):
    TestingSessionLocal, _, session = test_db
    detail = _create_advance(session, "cancel")
    visit_id = detail["id"]
    visit = _align_visit_schedule(session, visit_id)
    owner = _owner_ctx(session)
    db = TestingSessionLocal()
    approve_visit(db, owner, visit_id)
    session.refresh(visit)
    cancel_invitation(db, owner, visit_id, "Schedule changed")
    sec = _security_blr_ctx(session)
    result = verify_by_token(db, sec, visit.invitation_token)
    assert result["valid"] is False
    assert result["code"] == "CANCELLED"


def test_rejected_visit_has_no_valid_qr(test_db):
    TestingSessionLocal, _, session = test_db
    detail = _create_advance(session, "reject")
    visit_id = detail["id"]
    owner = _owner_ctx(session)
    db = TestingSessionLocal()
    reject_visit(db, owner, visit_id, "VISIT_NOT_AUTHORIZED", "Not approved")
    visit = session.get(Visit, visit_id)
    assert visit.status == VisitStatus.REJECTED.value
    assert not visit.invitation_active
    assert not visit.invitation_token


def test_badge_reprint_and_checkout_expire(test_db):
    TestingSessionLocal, _, session = test_db
    detail = _create_advance(session, "badgeflow")
    visit_id = detail["id"]
    _align_visit_schedule(session, visit_id)
    owner = _owner_ctx(session)
    sec = _security_blr_ctx(session)
    db = TestingSessionLocal()
    approve_visit(db, owner, visit_id)
    mark_arrived(db, sec, visit_id)
    check_in_visit(db, sec, visit_id)
    badge = issue_badge(db, sec, visit_id)
    number = badge["badge_number"]
    record_print(db, sec, visit_id)
    record_print(db, sec, visit_id, reprint=True)
    badge_row = session.query(VisitorBadge).filter(VisitorBadge.visit_id == visit_id).first()
    assert badge_row.badge_number == number
    assert badge_row.print_count >= 2
    check_out_visit(db, sec, visit_id)
    session.refresh(badge_row)
    assert badge_row.status == BadgeStatus.EXPIRED.value


def test_full_advance_visitor_e2e(test_db):
    TestingSessionLocal, _, session = test_db
    site_ctx = _site_admin_blr_ctx(session)
    detail = _create_advance(session, "e2e", ctx=site_ctx)
    visit_id = detail["id"]
    assert detail["status"] == VisitStatus.PENDING_APPROVAL.value
    assert detail["source"] == VisitSource.ADVANCE_REGISTRATION.value

    visit = _align_visit_schedule(session, visit_id)
    owner = _owner_ctx(session)
    sec = _security_blr_ctx(session)
    db = TestingSessionLocal()

    approve_visit(db, owner, visit_id)
    session.refresh(visit)
    assert visit.invitation_active is True
    assert visit.invitation_token

    public = get_public_invitation(db, visit.invitation_token)
    assert public["visitor_name"].startswith("Advance Visitor")

    verify = verify_by_token(db, sec, visit.invitation_token)
    assert verify["valid"] is True

    mark_arrived(db, sec, visit_id)
    check_in_visit(db, sec, visit_id)
    visit = db.get(Visit, visit_id)
    assert visit.status == VisitStatus.ONSITE.value

    badge = issue_badge(db, sec, visit_id)
    assert badge["badge_number"]

    check_out_visit(db, sec, visit_id)
    visit = db.get(Visit, visit_id)
    assert visit.status == VisitStatus.CHECKED_OUT.value
    badge_row = db.query(VisitorBadge).filter(VisitorBadge.visit_id == visit_id).first()
    assert badge_row.status == BadgeStatus.EXPIRED.value


def test_registration_rate_limit(client):
    c, _, session = client
    loc = session.query(Location).filter(Location.code == "BLR").first()
    token = loc.public_registration_token
    host_r = c.get(f"/api/public/sites/{token}/hosts?search=")
    host_id = host_r.json()[0]["id"]
    original = settings.rate_limit_registration_per_minute
    settings.rate_limit_registration_per_minute = 2
    payload = {
        "site_token": token,
        "visitor_type": "BUSINESS",
        "full_name": "Rate Limit Visitor",
        "mobile": "+91999001122",
        "email": "ratelimit@test.com",
        "company": "Co",
        "host_id": host_id,
        "purpose": "Test",
        "expected_duration_minutes": 60,
        "policy_accepted": True,
    }
    try:
        c.post("/api/public/registrations", json=payload)
        c.post("/api/public/registrations", json={**payload, "mobile": "+91999001123", "email": "ratelimit2@test.com"})
        blocked = c.post("/api/public/registrations", json={**payload, "mobile": "+91999001124", "email": "ratelimit3@test.com"})
        assert blocked.status_code == 429
        assert blocked.json()["error"]["code"] == "RATE_LIMITED"
    finally:
        settings.rate_limit_registration_per_minute = original
