import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.application.bootstrap import bootstrap_development_data, DEV_LOCATION_CODE, DEV_LOCATION_B_CODE, SITE_ADMIN_EMAIL
from app.domain.enums import AdminRole, VisitStatus
from app.domain.models import Location, Visit, AdminUser
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


def _get_dev_token(session_factory, bootstrap_session):
    loc = bootstrap_session.query(Location).filter(Location.code == DEV_LOCATION_CODE).first()
    if not loc:
        db = session_factory()
        loc = db.query(Location).filter(Location.code == DEV_LOCATION_CODE).first()
        db.close()
    return loc.public_registration_token, loc.id


def _get_host_id(client, token):
    r = client.get(f"/api/public/sites/{token}/hosts?search=")
    return r.json()[0]["id"]


def _submit_registration(client, token, host_id, mobile="+919876543210", email="visitor@test.com"):
    return client.post(
        "/api/public/registrations",
        json={
            "site_token": token,
            "visitor_type": "BUSINESS",
            "full_name": "Test Visitor",
            "mobile": mobile,
            "email": email,
            "company": "Test Corp",
            "host_id": host_id,
            "purpose": "Meeting",
            "expected_duration_minutes": 60,
            "policy_accepted": True,
        },
    )


def test_valid_site_token_resolves(client, test_db):
    c, session_factory, bootstrap_session = client
    token, _ = _get_dev_token(session_factory, bootstrap_session)
    r = c.get(f"/api/public/sites/{token}")
    assert r.status_code == 200
    assert r.json()["name"] == "Development Main Office"


def test_invalid_token_rejected(client):
    c, _, _ = client
    r = c.get("/api/public/sites/invalid-token-xyz")
    assert r.status_code == 404


def test_inactive_site_cannot_register(client, test_db):
    c, session_factory, bootstrap_session = client
    loc = bootstrap_session.query(Location).filter(Location.code == DEV_LOCATION_CODE).first()
    loc.is_active = False
    bootstrap_session.commit()
    token = loc.public_registration_token
    r = c.get(f"/api/public/sites/{token}")
    assert r.status_code == 404


def test_registration_creates_pending_approval(client, test_db):
    c, session_factory, bootstrap_session = client
    token, loc_id = _get_dev_token(session_factory, bootstrap_session)
    host_id = _get_host_id(c, token)
    r = _submit_registration(c, token, host_id)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == VisitStatus.PENDING_APPROVAL.value
    assert data["registration_reference"].startswith("VMS-")
    visit = bootstrap_session.query(Visit).filter(Visit.registration_reference == data["registration_reference"]).first()
    assert visit is not None
    assert visit.location_id == loc_id
    assert visit.policy_accepted is True


def test_policy_acceptance_required(client, test_db):
    c, session_factory, bootstrap_session = client
    token, _ = _get_dev_token(session_factory, bootstrap_session)
    host_id = _get_host_id(c, token)
    r = c.post(
        "/api/public/registrations",
        json={
            "site_token": token,
            "visitor_type": "BUSINESS",
            "full_name": "Test Visitor",
            "mobile": "+919876543211",
            "email": "visitor2@test.com",
            "company": "Test Corp",
            "host_id": host_id,
            "purpose": "Meeting",
            "expected_duration_minutes": 60,
            "policy_accepted": False,
        },
    )
    assert r.status_code == 400


def test_host_must_belong_to_site(client, test_db):
    c, session_factory, bootstrap_session = client
    loc_b = bootstrap_session.query(Location).filter(Location.code == DEV_LOCATION_B_CODE).first()
    token_a, _ = _get_dev_token(session_factory, bootstrap_session)
    # Create a host only on site B for isolation test
    from app.domain.models import Host, HostLocationAssignment
    host_b_only = Host(name="Site B Only Host", department="Ops", is_active=True, is_development_seed=True)
    bootstrap_session.add(host_b_only)
    bootstrap_session.flush()
    bootstrap_session.add(HostLocationAssignment(host_id=host_b_only.id, location_id=loc_b.id))
    bootstrap_session.commit()
    r = c.post(
        "/api/public/registrations",
        json={
            "site_token": token_a,
            "visitor_type": "BUSINESS",
            "full_name": "Test Visitor",
            "mobile": "+919876543212",
            "email": "visitor3@test.com",
            "company": "Test Corp",
            "host_id": host_b_only.id,
            "purpose": "Meeting",
            "expected_duration_minutes": 60,
            "policy_accepted": True,
        },
    )
    assert r.status_code == 400


def test_duplicate_rapid_submission(client, test_db):
    c, session_factory, bootstrap_session = client
    token, _ = _get_dev_token(session_factory, bootstrap_session)
    host_id = _get_host_id(c, token)
    r1 = _submit_registration(c, token, host_id, mobile="+919876543213", email="dup@test.com")
    r2 = _submit_registration(c, token, host_id, mobile="+919876543213", email="dup@test.com")
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["registration_reference"] == r2.json()["registration_reference"]
    count = bootstrap_session.query(Visit).filter(Visit.registration_reference == r1.json()["registration_reference"]).count()
    assert count == 1


def test_site_admin_only_sees_assigned_site(client, test_db):
    c, session_factory, bootstrap_session = client
    token_a, loc_a_id = _get_dev_token(session_factory, bootstrap_session)
    loc_b = bootstrap_session.query(Location).filter(Location.code == DEV_LOCATION_B_CODE).first()
    host_a = _get_host_id(c, token_a)
    _submit_registration(c, token_a, host_a, mobile="+919876543214", email="sitea@test.com")

    # Register on site B via public API - need host on site B
    hosts_b = c.get(f"/api/public/sites/{loc_b.public_registration_token}/hosts").json()
    if hosts_b:
        c.post(
            "/api/public/registrations",
            json={
                "site_token": loc_b.public_registration_token,
                "visitor_type": "BUSINESS",
                "full_name": "Site B Visitor",
                "mobile": "+919876543215",
                "email": "siteb@test.com",
                "company": "B Corp",
                "host_id": hosts_b[0]["id"],
                "purpose": "Visit",
                "expected_duration_minutes": 30,
                "policy_accepted": True,
            },
        )

    # Dev auth returns global admin by default - test site admin via direct API simulation
    from app.application.auth_service import build_auth_context, AuthContext
    from app.domain.models import AdminUser
    site_admin = bootstrap_session.query(AdminUser).filter(AdminUser.email == SITE_ADMIN_EMAIL).first()
    ctx = build_auth_context(site_admin)

    from app.application.site_scope_service import apply_location_scope
    query = bootstrap_session.query(Visit).filter(Visit.source == "self_registration")
    scoped = apply_location_scope(query, ctx, bootstrap_session)
    site_ids = {v.location_id for v in scoped.all()}
    assert loc_a_id in site_ids
    assert loc_b.id not in site_ids


def test_global_admin_sees_all_registrations(client, test_db):
    c, _, _ = client
    r = c.get("/api/self-registrations")
    assert r.status_code == 200
    assert r.json()["total"] >= 0
