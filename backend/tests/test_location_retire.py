"""Tests for safe location retirement (delete)."""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.application.bootstrap import bootstrap_development_data
from app.application.location_service import retire_location
from app.application.auth_service import build_auth_context
from app.core.config import settings
from app.domain.enums import EmergencyEventStatus, VisitStatus
from app.domain.models import AdminUser, EmergencyEvent, Location, UserLocationAssignment, Visit, Visitor, VisitorType, Host
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
    db.commit()
    yield TestingSessionLocal, db
    db.close()
    os.unlink(path)


@pytest.fixture
def client(test_db):
    TestingSessionLocal, bootstrap_session = test_db

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


def _owner_headers():
    return {"X-Dev-User-Email": "sheru.bohra@lazypay.in"}


def _head_headers():
    return {"X-Dev-User-Email": "headadmin@vms.local"}


def _site_admin_headers():
    return {"X-Dev-User-Email": "siteadmin.blr@vms.local"}


def _create_empty_location(client, monkeypatch, code="DTO"):
    c, _, _ = client
    monkeypatch.setattr(settings, "auth_mode", "dev")
    monkeypatch.setattr(settings, "dev_auth_enabled", True)
    resp = c.post(
        "/api/locations",
        headers=_owner_headers(),
        json={
            "name": "Delete Test Office",
            "code": code,
            "timezone": "Asia/Kolkata",
            "registration_enabled": True,
        },
    )
    assert resp.status_code == 201
    return resp.json()


def test_retire_empty_location(client, monkeypatch):
    c, TestingSessionLocal, _ = client
    monkeypatch.setattr(settings, "auth_mode", "dev")
    monkeypatch.setattr(settings, "dev_auth_enabled", True)
    loc = _create_empty_location(client, monkeypatch, "DEL1")
    loc_id = loc["id"]
    token = loc["public_registration_token"]

    summary = c.get(f"/api/locations/{loc_id}/retire-summary", headers=_owner_headers())
    assert summary.status_code == 200
    assert summary.json()["can_retire"] is True

    delete_resp = c.delete(f"/api/locations/{loc_id}", headers=_owner_headers())
    assert delete_resp.status_code == 200
    assert delete_resp.json()["status"] == "RETIRED"

    list_resp = c.get("/api/locations", headers=_owner_headers())
    assert all(row["id"] != loc_id for row in list_resp.json())

    db = TestingSessionLocal()
    retired = db.query(Location).filter(Location.id == loc_id).first()
    assert retired is not None
    assert retired.is_active is False
    assert retired.registration_enabled is False
    assert retired.public_registration_token == token
    db.close()

    public = c.get(f"/api/public/sites/{token}")
    assert public.status_code == 404


def test_head_admin_can_retire(client, monkeypatch):
    c, _, _ = client
    monkeypatch.setattr(settings, "auth_mode", "dev")
    monkeypatch.setattr(settings, "dev_auth_enabled", True)
    loc = _create_empty_location(client, monkeypatch, "HDL1")
    resp = c.delete(f"/api/locations/{loc['id']}", headers=_head_headers())
    assert resp.status_code == 200


def test_site_admin_cannot_retire(client, monkeypatch):
    c, _, session = client
    monkeypatch.setattr(settings, "auth_mode", "dev")
    monkeypatch.setattr(settings, "dev_auth_enabled", True)
    blr = session.query(Location).filter(Location.code == "BLR").first()
    resp = c.delete(f"/api/locations/{blr.id}", headers=_site_admin_headers())
    assert resp.status_code == 403


def test_retire_blocked_by_staff(client, monkeypatch):
    c, _, session = client
    monkeypatch.setattr(settings, "auth_mode", "dev")
    monkeypatch.setattr(settings, "dev_auth_enabled", True)
    loc = _create_empty_location(client, monkeypatch, "STF1")
    blr = session.query(Location).filter(Location.code == "BLR").first()
    site_admin = session.query(AdminUser).filter(AdminUser.email == "siteadmin.blr@vms.local").first()
    session.add(UserLocationAssignment(admin_user_id=site_admin.id, location_id=loc["id"]))
    session.commit()

    resp = c.delete(f"/api/locations/{loc['id']}", headers=_owner_headers())
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "LOCATION_HAS_ASSIGNED_STAFF"


def test_retire_blocked_by_onsite(client, monkeypatch):
    c, TestingSessionLocal, session = client
    monkeypatch.setattr(settings, "auth_mode", "dev")
    monkeypatch.setattr(settings, "dev_auth_enabled", True)
    loc_data = _create_empty_location(client, monkeypatch, "ONS1")
    loc = session.query(Location).filter(Location.code == "ONS1").first()
    vt = session.query(VisitorType).filter(VisitorType.code == "BUSINESS").first()
    host = session.query(Host).filter(Host.is_development_seed.is_(True)).first()
    visitor = Visitor(full_name="Onsite Guest", email="ons@g.com", phone="+9199000111", company="Co", visitor_type_id=vt.id)
    session.add(visitor)
    session.flush()
    visit = Visit(
        visitor_id=visitor.id,
        location_id=loc.id,
        status=VisitStatus.ONSITE.value,
        registration_reference="VMS-ONS-001",
        host_id=host.id,
        host_name=host.name,
        purpose="Test",
        expected_duration_minutes=60,
        policy_accepted=True,
        source="self_registration",
    )
    session.add(visit)
    session.commit()

    resp = c.delete(f"/api/locations/{loc.id}", headers=_owner_headers())
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "LOCATION_HAS_ONSITE_VISITORS"


def test_retire_allowed_with_historical_visit(client, monkeypatch):
    c, _, session = client
    monkeypatch.setattr(settings, "auth_mode", "dev")
    monkeypatch.setattr(settings, "dev_auth_enabled", True)
    loc_data = _create_empty_location(client, monkeypatch, "HIS1")
    loc = session.query(Location).filter(Location.code == "HIS1").first()
    vt = session.query(VisitorType).filter(VisitorType.code == "BUSINESS").first()
    host = session.query(Host).filter(Host.is_development_seed.is_(True)).first()
    visitor = Visitor(full_name="Past Guest", email="past@g.com", phone="+9199000222", company="Co", visitor_type_id=vt.id)
    session.add(visitor)
    session.flush()
    visit = Visit(
        visitor_id=visitor.id,
        location_id=loc.id,
        status=VisitStatus.CHECKED_OUT.value,
        registration_reference="VMS-HIS-001",
        host_id=host.id,
        host_name=host.name,
        purpose="Test",
        expected_duration_minutes=60,
        policy_accepted=True,
        source="self_registration",
    )
    session.add(visit)
    session.commit()

    resp = c.delete(f"/api/locations/{loc.id}", headers=_owner_headers())
    assert resp.status_code == 200


def test_double_retire_idempotent(client, monkeypatch):
    c, _, _ = client
    monkeypatch.setattr(settings, "auth_mode", "dev")
    monkeypatch.setattr(settings, "dev_auth_enabled", True)
    loc = _create_empty_location(client, monkeypatch, "DBL1")
    first = c.delete(f"/api/locations/{loc['id']}", headers=_owner_headers())
    second = c.delete(f"/api/locations/{loc['id']}", headers=_owner_headers())
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["status"] == "RETIRED"
