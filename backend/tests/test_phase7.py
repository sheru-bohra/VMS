import os
import tempfile
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.application.approval_service import ApprovalError, approve_visit
from app.application.auth_service import build_auth_context
from app.application.bootstrap import bootstrap_development_data
from app.application.invitation_service import create_advance_visit
from app.application.operations_service import check_in_visit, mark_arrived, OperationsError
from app.application.registration_service import create_self_registration
from app.application.security_review_service import resolve_clear
from app.application.security_screening_service import screen_visit
from app.application.visitor_qr_service import verify_by_token
from app.application.watchlist_service import (
    WatchlistError,
    create_watchlist_entry,
    deactivate_watchlist_entry,
)
from app.domain.enums import (
    AdminRole,
    Permission,
    SecurityClearanceStatus,
    SecurityResolution,
    VisitStatus,
    get_permissions_for_role,
)
from app.domain.models import AdminUser, Host, HostLocationAssignment, Location, Visit, Visitor, VisitorType
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


def _head_admin_ctx(session):
    user = session.query(AdminUser).filter(AdminUser.email == "headadmin@vms.local").first()
    return build_auth_context(user)


def _site_admin_blr_ctx(session):
    user = session.query(AdminUser).filter(AdminUser.email == "siteadmin.blr@vms.local").first()
    return build_auth_context(user)


def _security_blr_ctx(session):
    user = session.query(AdminUser).filter(AdminUser.email == "security.blr@vms.local").first()
    return build_auth_context(user)


def _security_mum_ctx(session):
    user = session.query(AdminUser).filter(AdminUser.email == "security.mum@vms.local").first()
    return build_auth_context(user)


def _blr_host(session):
    loc = session.query(Location).filter(Location.code == "BLR").first()
    ha = session.query(HostLocationAssignment).filter(HostLocationAssignment.location_id == loc.id).first()
    return ha.host_id, loc


def _register_self(session, suffix="wl", mobile="+919876543210", name="Rahul Sharma"):
    host_id, loc = _blr_host(session)
    return create_self_registration(
        session,
        site_token=loc.public_registration_token,
        visitor_type_code="BUSINESS",
        full_name=name,
        mobile=mobile,
        email=f"self{suffix}@test.com",
        company="ABC Ltd",
        host_id=host_id,
        purpose="Meeting",
        expected_duration_minutes=60,
        policy_accepted=True,
    )


def _visit_for_email(session, email: str) -> Visit:
    return session.query(Visit).join(Visitor).filter(Visitor.email == email).first()


def test_global_admin_can_create_global_watchlist(test_db):
    _, _, session = test_db
    ctx = _owner_ctx(session)
    entry = create_watchlist_entry(
        session, ctx,
        scope_type="GLOBAL",
        full_name="Blocked Person",
        mobile="+91999000001",
        reason_code="ACCESS_RESTRICTED",
        action_level="BLOCK",
        valid_from=datetime.now(timezone.utc),
    )
    assert entry["scope_type"] == "GLOBAL"
    assert entry["action_level"] == "BLOCK"


def test_security_cannot_create_watchlist(test_db):
    _, _, session = test_db
    ctx = _security_blr_ctx(session)
    with pytest.raises(WatchlistError) as exc:
        create_watchlist_entry(
            session, ctx,
            scope_type="GLOBAL",
            full_name="Test",
            mobile="+91999000002",
            reason_code="ACCESS_RESTRICTED",
            action_level="REVIEW",
            valid_from=datetime.now(timezone.utc),
        )
    assert exc.value.status_code == 403


def test_site_admin_cannot_create_global_watchlist(test_db):
    _, _, session = test_db
    ctx = _site_admin_blr_ctx(session)
    with pytest.raises(WatchlistError) as exc:
        create_watchlist_entry(
            session, ctx,
            scope_type="GLOBAL",
            full_name="Test",
            mobile="+91999000003",
            reason_code="ACCESS_RESTRICTED",
            action_level="REVIEW",
            valid_from=datetime.now(timezone.utc),
        )
    assert exc.value.status_code == 403


def test_inactive_watchlist_does_not_screen(test_db):
    TestingSessionLocal, _, session = test_db
    ctx = _owner_ctx(session)
    entry = create_watchlist_entry(
        session, ctx,
        scope_type="GLOBAL",
        full_name="Inactive Person",
        mobile="+91999000004",
        reason_code="ACCESS_RESTRICTED",
        action_level="BLOCK",
        valid_from=datetime.now(timezone.utc),
    )
    deactivate_watchlist_entry(session, ctx, entry["id"])
    create_self_registration(
        session,
        site_token=_blr_host(session)[1].public_registration_token,
        visitor_type_code="BUSINESS",
        full_name="Inactive Person",
        mobile="+91999000004",
        email="inactive@test.com",
        company="Co",
        host_id=_blr_host(session)[0],
        purpose="Test",
        expected_duration_minutes=60,
        policy_accepted=True,
    )
    visit = _visit_for_email(session, "inactive@test.com")
    assert visit.security_clearance_status == SecurityClearanceStatus.CLEAR.value


def test_exact_block_watchlist_e2e(test_db):
    TestingSessionLocal, _, session = test_db
    owner = _owner_ctx(session)
    sec = _security_blr_ctx(session)
    create_watchlist_entry(
        session, owner,
        scope_type="GLOBAL",
        full_name="Rahul Sharma",
        mobile="+919876543210",
        reason_code="PREVIOUS_SECURITY_INCIDENT",
        action_level="BLOCK",
        valid_from=datetime.now(timezone.utc),
    )
    _register_self(session, suffix="block", mobile="+919876543210", name="Rahul Sharma")
    visit = _visit_for_email(session, "selfblock@test.com")
    assert visit.security_clearance_status == SecurityClearanceStatus.BLOCKED.value

    with pytest.raises(ApprovalError) as exc:
        approve_visit(TestingSessionLocal(), owner, visit.id)
    assert exc.value.code == "SECURITY_ACCESS_BLOCKED"

    from app.application.security_review_service import get_security_review
    review = get_security_review(TestingSessionLocal(), sec, visit.id)
    assert review["security_status"] == "BLOCKED"
    assert review["signals"]


def test_possible_name_only_match_review_not_blocked(test_db):
    TestingSessionLocal, _, session = test_db
    owner = _owner_ctx(session)
    sec = _security_blr_ctx(session)
    create_watchlist_entry(
        session, owner,
        scope_type="GLOBAL",
        full_name="Similar Name Only",
        reason_code="ACCESS_RESTRICTED",
        action_level="BLOCK",
        valid_from=datetime.now(timezone.utc),
    )
    _register_self(session, suffix="possible", mobile="+91991112233", name="Similar Name Only")
    visit = _visit_for_email(session, "selfpossible@test.com")
    assert visit.security_clearance_status == SecurityClearanceStatus.REVIEW.value

    with pytest.raises(ApprovalError) as exc:
        approve_visit(TestingSessionLocal(), owner, visit.id)
    assert exc.value.code == "SECURITY_REVIEW_REQUIRED"

    resolve_clear(session, sec, visit.id, comment="Manual clear after review")
    session.refresh(visit)
    assert visit.security_clearance_status == SecurityClearanceStatus.CLEAR.value
    approve_visit(TestingSessionLocal(), owner, visit.id)


def test_watchlist_change_after_approval_rescreens_at_qr(test_db):
    TestingSessionLocal, _, session = test_db
    owner = _owner_ctx(session)
    sec = _security_blr_ctx(session)
    host_id, loc = _blr_host(session)
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")
    detail = create_advance_visit(
        session, owner,
        location_id=loc.id,
        visitor_type_code="BUSINESS",
        full_name="Advance Clear",
        mobile="9922233440",
        email="advanceclear@test.com",
        company="Co",
        host_id=host_id,
        visit_date=tomorrow,
        arrival_time="10:00",
        expected_duration_minutes=60,
        purpose="Meeting",
    )
    visit_id = detail["id"]
    visit = session.get(Visit, visit_id)
    visit.scheduled_start = datetime.now(timezone.utc) + timedelta(minutes=30)
    visit.scheduled_end = visit.scheduled_start + timedelta(hours=1)
    session.commit()
    approve_visit(TestingSessionLocal(), owner, visit_id)
    session.refresh(visit)
    assert visit.security_clearance_status == SecurityClearanceStatus.CLEAR.value

    create_watchlist_entry(
        session, owner,
        scope_type="GLOBAL",
        full_name="Advance Clear",
        mobile="9922233440",
        reason_code="ACCESS_RESTRICTED",
        action_level="BLOCK",
        valid_from=datetime.now(timezone.utc),
    )
    verify = verify_by_token(TestingSessionLocal(), sec, visit.invitation_token)
    assert verify["valid"] is False
    assert verify["code"] in ("SECURITY_BLOCKED", "SECURITY_REVIEW")


def test_duplicate_visitor_signal_no_merge(test_db):
    _, _, session = test_db
    vt = session.query(VisitorType).filter(VisitorType.code == "BUSINESS").first()
    v1 = Visitor(
        full_name="Original Visitor",
        phone="+91993334455",
        email="orig@test.com",
        company="Same Co",
        visitor_type_id=vt.id,
    )
    session.add(v1)
    session.commit()
    _register_self(session, suffix="dup", mobile="+91993334455", name="Original Visitor")
    visit = _visit_for_email(session, "selfdup@test.com")
    assert visit.security_clearance_status in (
        SecurityClearanceStatus.REVIEW.value,
        SecurityClearanceStatus.CLEAR.value,
    )
    count = session.query(Visitor).filter(Visitor.phone == "+91993334455").count()
    assert count >= 1


def test_security_blr_cannot_view_mumbai_review(client):
    c, TestingSessionLocal, session = client
    owner = _owner_ctx(session)
    mum = session.query(Location).filter(Location.code == "MUM").first()
    host = session.query(Host).filter(Host.is_development_seed.is_(True)).first()
    existing = session.query(HostLocationAssignment).filter(
        HostLocationAssignment.host_id == host.id,
        HostLocationAssignment.location_id == mum.id,
    ).first()
    if not existing:
        session.add(HostLocationAssignment(host_id=host.id, location_id=mum.id))
        session.commit()
    host_id = host.id
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")
    detail = create_advance_visit(
        session, owner,
        location_id=mum.id,
        visitor_type_code="BUSINESS",
        full_name="Mumbai Visitor",
        mobile="9944455660",
        email="mumbai@test.com",
        company="Co",
        host_id=host_id,
        visit_date=tomorrow,
        arrival_time="11:00",
        expected_duration_minutes=60,
        purpose="Meeting",
    )
    visit_id = detail["id"]
    create_watchlist_entry(
        session, owner,
        scope_type="GLOBAL",
        full_name="Mumbai Visitor",
        mobile="9944455660",
        reason_code="ACCESS_RESTRICTED",
        action_level="BLOCK",
        valid_from=datetime.now(timezone.utc),
    )
    screen_visit(session, visit_id)
    blr_headers = {"X-Dev-User-Email": "security.blr@vms.local"}
    r = c.get(f"/api/security-reviews/{visit_id}", headers=blr_headers)
    assert r.status_code == 403


def test_checkin_blocked_when_security_review_pending(test_db):
    TestingSessionLocal, _, session = test_db
    owner = _owner_ctx(session)
    sec = _security_blr_ctx(session)
    create_watchlist_entry(
        session, owner,
        scope_type="GLOBAL",
        full_name="Checkin Block",
        mobile="+91995556677",
        reason_code="ACCESS_RESTRICTED",
        action_level="REVIEW",
        valid_from=datetime.now(timezone.utc),
    )
    _register_self(session, suffix="checkin", mobile="+91995556677", name="Checkin Block")
    visit = _visit_for_email(session, "selfcheckin@test.com")
    assert visit.security_clearance_status == SecurityClearanceStatus.REVIEW.value
    visit.status = VisitStatus.ARRIVED.value
    visit.scheduled_start = datetime.now(timezone.utc) - timedelta(minutes=5)
    visit.scheduled_end = datetime.now(timezone.utc) + timedelta(hours=1)
    session.commit()
    db = TestingSessionLocal()
    with pytest.raises(OperationsError) as exc:
        check_in_visit(db, sec, visit.id)
    assert exc.value.code == "SECURITY_REVIEW_REQUIRED"
    db.close()

    resolve_clear(session, sec, visit.id)
    visit.status = VisitStatus.PENDING_APPROVAL.value
    session.commit()
    db = TestingSessionLocal()
    approve_visit(db, owner, visit.id)
    mark_arrived(db, sec, visit.id)
    result = check_in_visit(db, sec, visit.id)
    db.close()
    assert result["status"] == VisitStatus.ONSITE.value


def test_security_role_permissions_regression(test_db):
    perms = get_permissions_for_role(AdminRole.SECURITY)
    assert Permission.WATCHLIST_READ in perms
    assert Permission.WATCHLIST_CREATE not in perms
    assert Permission.REPORTS_VIEW not in perms
    assert Permission.ANALYTICS_WEEKLY_VIEW not in perms


def test_watchlist_api_list(client):
    c, _, _ = client
    headers = {"X-Dev-User-Email": "security.blr@vms.local"}
    r = c.get("/api/watchlist", headers=headers)
    assert r.status_code == 200
    assert "items" in r.json()


def test_security_cannot_create_via_api(client):
    c, _, _ = client
    headers = {"X-Dev-User-Email": "security.blr@vms.local"}
    payload = {
        "scope_type": "GLOBAL",
        "full_name": "API Test",
        "mobile": "+91996667788",
        "reason_code": "ACCESS_RESTRICTED",
        "action_level": "REVIEW",
        "valid_from": datetime.now(timezone.utc).isoformat(),
    }
    r = c.post("/api/watchlist", json=payload, headers=headers)
    assert r.status_code == 403
