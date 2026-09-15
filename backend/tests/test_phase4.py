import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.application.auth_service import build_auth_context
from app.application.bootstrap import bootstrap_development_data, DEV_LOCATION_CODE
from app.application.operations_service import (
    check_in_visit,
    check_out_visit,
    mark_arrived,
)
from app.application.approval_service import approve_visit
from app.domain.enums import AdminRole, Permission, VisitStatus, get_permissions_for_role, role_has_permission
from app.domain.models import AdminUser, Location, Visit, Visitor, VisitorType, Host
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


def _create_approved_visit(session, location_code: str, suffix: str = "1"):
    loc = session.query(Location).filter(Location.code == location_code).first()
    vt = session.query(VisitorType).filter(VisitorType.code == "BUSINESS").first()
    host = session.query(Host).filter(Host.is_development_seed.is_(True)).first()
    visitor = Visitor(
        full_name=f"Ops Visitor {suffix}",
        email=f"ops{suffix}@test.com",
        phone=f"+91988{suffix}00000",
        company="Ops Co",
        visitor_type_id=vt.id,
    )
    session.add(visitor)
    session.flush()
    visit = Visit(
        visitor_id=visitor.id,
        location_id=loc.id,
        status=VisitStatus.APPROVED.value,
        registration_reference=f"VMS-OPS-{suffix}",
        host_id=host.id,
        host_name=host.name,
        purpose="Meeting",
        expected_duration_minutes=60,
        policy_accepted=True,
        source="self_registration",
    )
    session.add(visit)
    session.commit()
    session.refresh(visit)
    return visit, loc


def _user_ctx(session, email: str):
    user = session.query(AdminUser).filter(AdminUser.email == email).first()
    return build_auth_context(user)


def test_security_role_permissions():
    perms = get_permissions_for_role(AdminRole.SECURITY)
    assert Permission.ARRIVAL_MANAGE in perms
    assert Permission.CHECKIN_PERFORM in perms
    assert Permission.CHECKOUT_PERFORM in perms
    assert Permission.APPROVAL_APPROVE in perms
    assert Permission.REPORTS_VIEW not in perms
    assert Permission.ANALYTICS_WEEKLY_VIEW not in perms
    assert Permission.LOCATIONS_MANAGE not in perms
    assert Permission.ADMINS_READ not in perms


def test_approved_visit_can_be_marked_arrived(test_db):
    TestingSessionLocal, _, session = test_db
    visit, _ = _create_approved_visit(session, "BLR", "arrive")
    ctx = _user_ctx(session, "sheru.bohra@lazypay.in")
    db = TestingSessionLocal()
    result = mark_arrived(db, ctx, visit.id)
    assert result["status"] == VisitStatus.ARRIVED.value
    assert result["arrived_at"] is not None


def test_arrived_visitor_can_check_in(test_db):
    TestingSessionLocal, _, session = test_db
    visit, _ = _create_approved_visit(session, "BLR", "checkin")
    ctx = _user_ctx(session, "sheru.bohra@lazypay.in")
    db = TestingSessionLocal()
    mark_arrived(db, ctx, visit.id)
    result = check_in_visit(db, ctx, visit.id)
    assert result["status"] == VisitStatus.ONSITE.value
    assert result["checked_in_at"] is not None


def test_rejected_visitor_cannot_check_in(test_db):
    TestingSessionLocal, _, session = test_db
    visit, _ = _create_approved_visit(session, "BLR", "rej")
    visit.status = VisitStatus.REJECTED.value
    session.commit()
    ctx = _user_ctx(session, "sheru.bohra@lazypay.in")
    db = TestingSessionLocal()
    from app.application.operations_service import OperationsError
    with pytest.raises(OperationsError) as exc:
        check_in_visit(db, ctx, visit.id)
    assert exc.value.status_code == 409


def test_onsite_visitor_can_check_out(test_db):
    TestingSessionLocal, _, session = test_db
    visit, _ = _create_approved_visit(session, "BLR", "checkout")
    ctx = _user_ctx(session, "sheru.bohra@lazypay.in")
    db = TestingSessionLocal()
    mark_arrived(db, ctx, visit.id)
    check_in_visit(db, ctx, visit.id)
    result = check_out_visit(db, ctx, visit.id)
    assert result["status"] == VisitStatus.CHECKED_OUT.value
    assert result["checked_out_at"] is not None


def test_double_checkout_idempotent(test_db):
    TestingSessionLocal, _, session = test_db
    visit, _ = _create_approved_visit(session, "BLR", "double")
    ctx = _user_ctx(session, "sheru.bohra@lazypay.in")
    db = TestingSessionLocal()
    mark_arrived(db, ctx, visit.id)
    check_in_visit(db, ctx, visit.id)
    check_out_visit(db, ctx, visit.id)
    result = check_out_visit(db, ctx, visit.id)
    assert result["status"] == VisitStatus.CHECKED_OUT.value


def test_security_bangalore_can_operate_bangalore(test_db):
    TestingSessionLocal, _, session = test_db
    visit, _ = _create_approved_visit(session, "BLR", "secblr")
    ctx = _user_ctx(session, "security.blr@vms.local")
    db = TestingSessionLocal()
    mark_arrived(db, ctx, visit.id)
    result = check_in_visit(db, ctx, visit.id)
    assert result["status"] == VisitStatus.ONSITE.value


def test_security_bangalore_cannot_operate_mumbai(test_db):
    TestingSessionLocal, _, session = test_db
    visit, _ = _create_approved_visit(session, "MUM", "secmum")
    ctx = _user_ctx(session, "security.blr@vms.local")
    db = TestingSessionLocal()
    from app.application.operations_service import OperationsError
    with pytest.raises(OperationsError) as exc:
        mark_arrived(db, ctx, visit.id)
    assert exc.value.status_code == 403


def test_security_api_cross_location_blocked(client):
    c, TestingSessionLocal, session = client
    visit, _ = _create_approved_visit(session, "MUM", "apimum")
    response = c.post(
        f"/api/visits/{visit.id}/arrive",
        headers={"X-Dev-User-Email": "security.blr@vms.local"},
    )
    assert response.status_code == 403


def test_expected_today_lists_approved(client):
    c, TestingSessionLocal, session = client
    _create_approved_visit(session, "BLR", "today")
    response = c.get("/api/expected-today", params={"site": session.query(Location).filter(Location.code == "BLR").first().id})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1


def test_onsite_count_scoped(client):
    c, TestingSessionLocal, session = client
    visit, loc = _create_approved_visit(session, "BLR", "onsitecnt")
    owner = _user_ctx(session, "sheru.bohra@lazypay.in")
    db = TestingSessionLocal()
    mark_arrived(db, owner, visit.id)
    check_in_visit(db, owner, visit.id)
    response = c.get("/api/onsite", params={"site": loc.id})
    assert response.status_code == 200
    assert response.json()["onsite_count"] >= 1


def test_visitor_list_api(client):
    c, TestingSessionLocal, session = client
    _create_approved_visit(session, "BLR", "visitorlist")
    blr = session.query(Location).filter(Location.code == "BLR").first()
    response = c.get("/api/visitors", params={"site": blr.id})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert any(item["visitor_name"] for item in data["items"])


def test_office_locations_seeded(test_db):
    _, _, session = test_db
    codes = ["BLR", "GGN", "NOI", "MUM", "PUN"]
    for code in codes:
        loc = session.query(Location).filter(Location.code == code).first()
        assert loc is not None
        assert loc.timezone == "Asia/Kolkata"
        assert loc.public_registration_token is not None
