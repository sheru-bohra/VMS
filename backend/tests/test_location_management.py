"""Tests for location management and site staff assignment."""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.application.bootstrap import bootstrap_development_data
from app.application.location_staff_service import assign_location_staff
from app.application.auth_service import build_auth_context
from app.core.config import settings
from app.domain.models import AdminUser, Location, UserLocationAssignment
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


def _security_headers():
    return {"X-Dev-User-Email": "security.blr@vms.local"}


def test_global_admin_creates_location(client, monkeypatch):
    c, _, _ = client
    monkeypatch.setattr(settings, "auth_mode", "dev")
    monkeypatch.setattr(settings, "dev_auth_enabled", True)
    resp = c.post(
        "/api/locations",
        headers=_owner_headers(),
        json={
            "name": "Test Corporate Office",
            "code": "TCO",
            "timezone": "Asia/Kolkata",
            "registration_enabled": True,
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["code"] == "TCO"
    assert body["name"] == "Test Corporate Office"
    assert body["public_registration_token"]
    assert body["registration_url"]


def test_head_admin_creates_location(client, monkeypatch):
    c, _, _ = client
    monkeypatch.setattr(settings, "auth_mode", "dev")
    monkeypatch.setattr(settings, "dev_auth_enabled", True)
    resp = c.post(
        "/api/locations",
        headers=_head_headers(),
        json={
            "name": "Head Created Office",
            "code": "HCO",
            "timezone": "Asia/Kolkata",
            "registration_enabled": True,
        },
    )
    assert resp.status_code == 201


def test_site_admin_cannot_create_location(client, monkeypatch):
    c, _, _ = client
    monkeypatch.setattr(settings, "auth_mode", "dev")
    monkeypatch.setattr(settings, "dev_auth_enabled", True)
    resp = c.post(
        "/api/locations",
        headers=_site_admin_headers(),
        json={
            "name": "Blocked Office",
            "code": "BLK",
            "timezone": "Asia/Kolkata",
            "registration_enabled": True,
        },
    )
    assert resp.status_code == 403


def test_security_cannot_create_location(client, monkeypatch):
    c, _, _ = client
    monkeypatch.setattr(settings, "auth_mode", "dev")
    monkeypatch.setattr(settings, "dev_auth_enabled", True)
    resp = c.post(
        "/api/locations",
        headers=_security_headers(),
        json={
            "name": "Blocked Office 2",
            "code": "BLK2",
            "timezone": "Asia/Kolkata",
            "registration_enabled": True,
        },
    )
    assert resp.status_code == 403


def test_duplicate_location_code_rejected(client, monkeypatch):
    c, _, session = client
    monkeypatch.setattr(settings, "auth_mode", "dev")
    monkeypatch.setattr(settings, "dev_auth_enabled", True)
    blr = session.query(Location).filter(Location.code == "BLR").first()
    resp = c.post(
        "/api/locations",
        headers=_owner_headers(),
        json={
            "name": "Duplicate BLR",
            "code": blr.code,
            "timezone": "Asia/Kolkata",
            "registration_enabled": True,
        },
    )
    assert resp.status_code == 409


def test_head_assigns_site_admin_to_location(client, monkeypatch):
    c, TestingSessionLocal, session = client
    monkeypatch.setattr(settings, "auth_mode", "dev")
    monkeypatch.setattr(settings, "dev_auth_enabled", True)
    blr = session.query(Location).filter(Location.code == "BLR").first()
    resp = c.post(
        f"/api/locations/{blr.id}/staff",
        headers=_head_headers(),
        json={
            "email": "siteadmin.tco@example.invalid",
            "display_name": "TCO Site Admin",
            "role": "SITE_ADMIN",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "siteadmin.tco@example.invalid"
    assert body["role"] == "SITE_ADMIN"

    db = TestingSessionLocal()
    user = db.query(AdminUser).filter(AdminUser.email == "siteadmin.tco@example.invalid").first()
    assert user is not None
    assignment = (
        db.query(UserLocationAssignment)
        .filter(UserLocationAssignment.admin_user_id == user.id, UserLocationAssignment.location_id == blr.id)
        .first()
    )
    assert assignment is not None
    db.close()


def test_cannot_assign_global_admin_through_location_staff(client, monkeypatch):
    c, _, session = client
    monkeypatch.setattr(settings, "auth_mode", "dev")
    monkeypatch.setattr(settings, "dev_auth_enabled", True)
    blr = session.query(Location).filter(Location.code == "BLR").first()
    owner = session.query(AdminUser).filter(AdminUser.email == "sheru.bohra@lazypay.in").first()
    resp = c.post(
        f"/api/locations/{blr.id}/staff",
        headers=_head_headers(),
        json={
            "email": owner.email,
            "display_name": "Owner",
            "role": "SITE_ADMIN",
        },
    )
    assert resp.status_code in (400, 403)


def test_reject_global_admin_role_in_payload(client, monkeypatch):
    c, _, session = client
    monkeypatch.setattr(settings, "auth_mode", "dev")
    monkeypatch.setattr(settings, "dev_auth_enabled", True)
    blr = session.query(Location).filter(Location.code == "BLR").first()
    resp = c.post(
        f"/api/locations/{blr.id}/staff",
        headers=_owner_headers(),
        json={
            "email": "new.global@example.invalid",
            "display_name": "New Global",
            "role": "GLOBAL_ADMIN",
        },
    )
    assert resp.status_code == 400


def test_malicious_is_owner_field_rejected(client, monkeypatch):
    c, _, session = client
    monkeypatch.setattr(settings, "auth_mode", "dev")
    monkeypatch.setattr(settings, "dev_auth_enabled", True)
    blr = session.query(Location).filter(Location.code == "BLR").first()
    resp = c.post(
        f"/api/locations/{blr.id}/staff",
        headers=_owner_headers(),
        json={
            "email": "malicious@example.invalid",
            "display_name": "Malicious",
            "role": "SITE_ADMIN",
            "is_owner": True,
        },
    )
    assert resp.status_code == 422


def test_remove_assignment_preserves_other_locations(client, monkeypatch):
    c, TestingSessionLocal, session = client
    monkeypatch.setattr(settings, "auth_mode", "dev")
    monkeypatch.setattr(settings, "dev_auth_enabled", True)
    blr = session.query(Location).filter(Location.code == "BLR").first()
    mum = session.query(Location).filter(Location.code == "MUM").first()
    db = TestingSessionLocal()
    head = session.query(AdminUser).filter(AdminUser.email == "headadmin@vms.local").first()
    ctx = build_auth_context(head)
    assign_location_staff(
        db,
        ctx,
        blr.id,
        "multi.site@example.invalid",
        "Multi Site",
        "SITE_ADMIN",
    )
    user = db.query(AdminUser).filter(AdminUser.email == "multi.site@example.invalid").first()
    user_id = user.id
    db.add(UserLocationAssignment(admin_user_id=user_id, location_id=mum.id))
    db.commit()
    db.close()

    resp = c.delete(
        f"/api/locations/{blr.id}/staff/{user_id}",
        headers=_owner_headers(),
    )
    assert resp.status_code == 204

    db = TestingSessionLocal()
    blr_assignment = (
        db.query(UserLocationAssignment)
        .filter(UserLocationAssignment.admin_user_id == user_id, UserLocationAssignment.location_id == blr.id)
        .first()
    )
    mum_assignment = (
        db.query(UserLocationAssignment)
        .filter(UserLocationAssignment.admin_user_id == user_id, UserLocationAssignment.location_id == mum.id)
        .first()
    )
    assert blr_assignment is None
    assert mum_assignment is not None
    assert db.query(AdminUser).filter(AdminUser.id == user_id).first().is_active
    db.close()


def test_duplicate_assignment_idempotent(client, monkeypatch):
    c, _, session = client
    monkeypatch.setattr(settings, "auth_mode", "dev")
    monkeypatch.setattr(settings, "dev_auth_enabled", True)
    blr = session.query(Location).filter(Location.code == "BLR").first()
    payload = {
        "email": "dup.assign@example.invalid",
        "display_name": "Dup Assign",
        "role": "SECURITY",
    }
    first = c.post(f"/api/locations/{blr.id}/staff", headers=_owner_headers(), json=payload)
    second = c.post(f"/api/locations/{blr.id}/staff", headers=_owner_headers(), json=payload)
    assert first.status_code == 201
    assert second.status_code == 201
    db_session = session
    user = db_session.query(AdminUser).filter(AdminUser.email == "dup.assign@example.invalid").first()
    count = (
        db_session.query(UserLocationAssignment)
        .filter(UserLocationAssignment.admin_user_id == user.id, UserLocationAssignment.location_id == blr.id)
        .count()
    )
    assert count == 1


def test_site_admin_cannot_manage_location_staff(client, monkeypatch):
    c, _, session = client
    monkeypatch.setattr(settings, "auth_mode", "dev")
    monkeypatch.setattr(settings, "dev_auth_enabled", True)
    blr = session.query(Location).filter(Location.code == "BLR").first()
    resp = c.get(f"/api/locations/{blr.id}/staff", headers=_site_admin_headers())
    assert resp.status_code == 403
