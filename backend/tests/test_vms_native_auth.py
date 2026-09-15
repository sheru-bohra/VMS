"""VMS native authentication for all staff."""

import os
import tempfile
from typing import Optional

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.domain.models  # noqa: F401
from app.application.bootstrap import LEGACY_OWNER_EMAIL, OWNER_EMAIL, bootstrap_development_data
from app.application.password_service import hash_password
from app.application.vms_native_auth_service import VMS_NATIVE_AUTH_PROVIDER, issue_vms_native_token
from app.core.config import settings
from app.domain.enums import AdminRole
from app.domain.models import AdminUser, Location, UserLocationAssignment
from app.infrastructure.database import Base, get_db
from app.main import create_app

TEST_PASSWORD = "Test-Staff-Password-12"
HEAD_PASSWORD = "Head-Admin-Password-12"
SITE_PASSWORD = "Site-Admin-Password-12"
SEC_PASSWORD = "Security-Password-12"


@pytest.fixture
def test_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    yield TestingSessionLocal, engine
    os.unlink(path)


@pytest.fixture
def client(test_db, monkeypatch):
    TestingSessionLocal, _ = test_db
    monkeypatch.setattr(settings, "auth_mode", "vms_native")
    monkeypatch.setattr(settings, "vms_native_auth_enabled", True)
    monkeypatch.setattr(settings, "global_admin_initial_password", TEST_PASSWORD)
    monkeypatch.setattr(settings, "vms_data_encryption_key", "test-vms-native-session-secret-32b")
    monkeypatch.setattr(
        "app.application.vms_native_auth_service.check_vms_native_login_rate_limit",
        lambda request, email: None,
    )

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c, TestingSessionLocal
    app.dependency_overrides.clear()


def _seed(db):
    bootstrap_development_data(db)
    owner = db.query(AdminUser).filter(AdminUser.email == OWNER_EMAIL).first()
    assert owner is not None
    db.commit()
    return owner


def _staff(db, email: str, role: AdminRole, password: str, location_code: Optional[str] = None):
    user = AdminUser(
        email=email,
        display_name=role.value,
        role=role.value,
        is_owner=False,
        is_active=True,
        auth_provider=VMS_NATIVE_AUTH_PROVIDER,
        password_hash=hash_password(password),
        force_password_change=False,
    )
    db.add(user)
    db.flush()
    if location_code:
        loc = db.query(Location).filter(Location.code == location_code).first()
        if loc:
            db.add(UserLocationAssignment(admin_user_id=user.id, location_id=loc.id))
    db.commit()
    return user


def _login(c, email: str, password: str):
    return c.post("/api/auth/login", json={"email": email, "password": password})


def test_global_admin_login_success(client):
    c, session_factory = client
    db = session_factory()
    _seed(db)
    db.close()

    response = _login(c, OWNER_EMAIL, TEST_PASSWORD)
    assert response.status_code == 200
    token = response.json()["access_token"]
    me = c.get("/api/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    data = me.json()
    assert data["email"] == OWNER_EMAIL
    assert data["role"] == AdminRole.GLOBAL_ADMIN.value
    assert data["is_owner"] is True
    assert data["auth_provider"] == VMS_NATIVE_AUTH_PROVIDER


def test_legacy_owner_email_fails(client):
    c, session_factory = client
    db = session_factory()
    _seed(db)
    db.close()
    assert _login(c, LEGACY_OWNER_EMAIL, TEST_PASSWORD).status_code == 401


def test_head_admin_login_success(client):
    c, session_factory = client
    db = session_factory()
    _seed(db)
    _staff(db, "headadmin@test.local", AdminRole.HEAD_ADMIN, HEAD_PASSWORD)
    db.close()
    assert _login(c, "headadmin@test.local", HEAD_PASSWORD).status_code == 200


def test_site_admin_login_success(client):
    c, session_factory = client
    db = session_factory()
    _seed(db)
    _staff(db, "siteadmin@test.local", AdminRole.SITE_ADMIN, SITE_PASSWORD, "BLR")
    db.close()
    assert _login(c, "siteadmin@test.local", SITE_PASSWORD).status_code == 200


def test_security_login_success(client):
    c, session_factory = client
    db = session_factory()
    _seed(db)
    _staff(db, "security@test.local", AdminRole.SECURITY, SEC_PASSWORD, "BLR")
    db.close()
    assert _login(c, "security@test.local", SEC_PASSWORD).status_code == 200


def test_unknown_user_fails(client):
    c, _ = client
    response = _login(c, "unknown@lazypay.in", TEST_PASSWORD)
    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Invalid email or password."


def test_inactive_user_fails(client):
    c, session_factory = client
    db = session_factory()
    owner = _seed(db)
    owner.is_active = False
    db.commit()
    db.close()
    assert _login(c, OWNER_EMAIL, TEST_PASSWORD).status_code == 401


def test_password_reset_invalidates_session(client):
    c, session_factory = client
    db = session_factory()
    _seed(db)
    staff = _staff(db, "siteadmin@test.local", AdminRole.SITE_ADMIN, SITE_PASSWORD, "BLR")
    staff_id = staff.id
    db.close()

    login = _login(c, "siteadmin@test.local", SITE_PASSWORD)
    token = login.json()["access_token"]
    owner_login = _login(c, OWNER_EMAIL, TEST_PASSWORD)
    owner_token = owner_login.json()["access_token"]

    c.post(
        f"/api/administration/users/{staff_id}/reset-password",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "temporary_password": "New-Temp-Password-12",
            "confirm_password": "New-Temp-Password-12",
            "force_password_change": True,
        },
    )
    assert c.get("/api/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_head_admin_cannot_manage_users(client):
    c, session_factory = client
    db = session_factory()
    _seed(db)
    _staff(db, "headadmin@test.local", AdminRole.HEAD_ADMIN, HEAD_PASSWORD)
    db.close()

    login = _login(c, "headadmin@test.local", HEAD_PASSWORD)
    token = login.json()["access_token"]
    response = c.post(
        "/api/administration/users",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "email": "newuser@test.local",
            "display_name": "New User",
            "role": "SITE_ADMIN",
            "location_ids": [],
            "generate_password": True,
        },
    )
    assert response.status_code == 403


def test_owner_protection(client):
    c, session_factory = client
    db = session_factory()
    owner = _seed(db)
    owner_id = owner.id
    db.close()

    login = _login(c, OWNER_EMAIL, TEST_PASSWORD)
    token = login.json()["access_token"]
    deactivate = c.post(
        f"/api/administration/users/{owner_id}/deactivate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert deactivate.status_code == 403


def test_force_password_change_blocks_protected_routes(client):
    c, session_factory = client
    db = session_factory()
    _seed(db)
    staff = _staff(db, "siteadmin@test.local", AdminRole.SITE_ADMIN, SITE_PASSWORD, "BLR")
    staff.force_password_change = True
    db.commit()
    db.close()

    login = _login(c, "siteadmin@test.local", SITE_PASSWORD)
    token = login.json()["access_token"]
    blocked = c.get("/api/locations", headers={"Authorization": f"Bearer {token}"})
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "PASSWORD_CHANGE_REQUIRED"


def test_set_password_completes_first_login(client):
    c, session_factory = client
    db = session_factory()
    _seed(db)
    staff = _staff(db, "siteadmin@test.local", AdminRole.SITE_ADMIN, SITE_PASSWORD, "BLR")
    staff.force_password_change = True
    db.commit()
    db.close()

    login = _login(c, "siteadmin@test.local", SITE_PASSWORD)
    token = login.json()["access_token"]
    set_pw = c.post(
        "/api/auth/set-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"new_password": "Updated-Password-12", "confirm_password": "Updated-Password-12"},
    )
    assert set_pw.status_code == 200
    me = c.get("/api/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["force_password_change"] is False


def test_api_never_returns_password_hash(client):
    c, session_factory = client
    db = session_factory()
    _seed(db)
    db.close()
    login = _login(c, OWNER_EMAIL, TEST_PASSWORD)
    token = login.json()["access_token"]
    users = c.get("/api/administration/users", headers={"Authorization": f"Bearer {token}"})
    assert "password_hash" not in users.text
    assert TEST_PASSWORD not in users.text


def test_global_admin_self_password_change(client):
    c, session_factory = client
    db = session_factory()
    _seed(db)
    db.close()

    login = _login(c, OWNER_EMAIL, TEST_PASSWORD)
    token = login.json()["access_token"]
    new_password = "Owner-New-Password-12"
    change = c.post(
        "/api/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_password": TEST_PASSWORD,
            "new_password": new_password,
            "confirm_password": new_password,
        },
    )
    assert change.status_code == 200
    assert c.get("/api/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    assert _login(c, OWNER_EMAIL, new_password).status_code == 200


def test_global_admin_resets_owner_password(client):
    c, session_factory = client
    db = session_factory()
    owner = _seed(db)
    owner_id = owner.id
    db.close()

    login = _login(c, OWNER_EMAIL, TEST_PASSWORD)
    token = login.json()["access_token"]
    temp_password = "Owner-Reset-Password-12"
    reset = c.post(
        f"/api/administration/users/{owner_id}/reset-password",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "temporary_password": temp_password,
            "confirm_password": temp_password,
            "force_password_change": False,
        },
    )
    assert reset.status_code == 200
    assert _login(c, OWNER_EMAIL, temp_password).status_code == 200


def test_site_admin_cannot_change_password_endpoint(client):
    c, session_factory = client
    db = session_factory()
    _seed(db)
    _staff(db, "siteadmin@test.local", AdminRole.SITE_ADMIN, SITE_PASSWORD, "BLR")
    db.close()

    login = _login(c, "siteadmin@test.local", SITE_PASSWORD)
    token = login.json()["access_token"]
    change = c.post(
        "/api/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_password": SITE_PASSWORD,
            "new_password": "Site-New-Password-12",
            "confirm_password": "Site-New-Password-12",
        },
    )
    assert change.status_code == 403


def test_site_admin_cannot_reset_other_password(client):
    c, session_factory = client
    db = session_factory()
    _seed(db)
    _staff(db, "siteadmin@test.local", AdminRole.SITE_ADMIN, SITE_PASSWORD, "BLR")
    _staff(db, "security@test.local", AdminRole.SECURITY, SEC_PASSWORD, "BLR")
    security = db.query(AdminUser).filter(AdminUser.email == "security@test.local").first()
    security_id = security.id
    db.close()

    login = _login(c, "siteadmin@test.local", SITE_PASSWORD)
    token = login.json()["access_token"]
    reset = c.post(
        f"/api/administration/users/{security_id}/reset-password",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "temporary_password": "Blocked-Reset-Password-12",
            "confirm_password": "Blocked-Reset-Password-12",
        },
    )
    assert reset.status_code == 403


def test_short_bootstrap_password_requires_change(client, monkeypatch):
    c, session_factory = client
    monkeypatch.setattr(settings, "global_admin_initial_password", "shortpw")
    db = session_factory()
    _seed(db)
    owner = db.query(AdminUser).filter(AdminUser.email == OWNER_EMAIL).first()
    assert owner.force_password_change is True
    db.close()

    login = _login(c, OWNER_EMAIL, "shortpw")
    assert login.status_code == 200
    assert login.json()["force_password_change"] is True


def test_owner_stale_hash_reprovisioned_from_env(client, monkeypatch):
    c, session_factory = client
    monkeypatch.setattr(settings, "global_admin_initial_password", TEST_PASSWORD)
    db = session_factory()
    from app.application.bootstrap import ensure_permanent_owner
    from app.application.password_service import hash_password

    owner = ensure_permanent_owner(db)
    owner.password_hash = hash_password("Stale-Password-From-Old-Phase-12")
    owner.initial_credential_provisioned_at = None
    owner.password_changed_at = None
    owner.force_password_change = False
    db.commit()
    db.close()

    db = session_factory()
    from app.application.bootstrap import ensure_permanent_owner as reprovision

    reprovision(db)
    db.commit()
    owner = db.query(AdminUser).filter(AdminUser.email == OWNER_EMAIL).first()
    assert owner.initial_credential_provisioned_at is not None
    db.close()

    assert _login(c, OWNER_EMAIL, TEST_PASSWORD).status_code == 200


def test_owner_password_not_reset_after_established_credential(client, monkeypatch):
    c, session_factory = client
    monkeypatch.setattr(settings, "global_admin_initial_password", TEST_PASSWORD)
    custom_password = "Owner-Custom-Password-12"
    db = session_factory()
    from app.application.bootstrap import ensure_permanent_owner
    from app.application.vms_native_auth_service import set_user_password

    owner = ensure_permanent_owner(db)
    set_user_password(db, owner, custom_password, clear_force_change=True)
    db.commit()
    db.close()

    db = session_factory()
    from app.application.bootstrap import ensure_permanent_owner as reprovision

    reprovision(db)
    db.commit()
    db.close()

    assert _login(c, OWNER_EMAIL, custom_password).status_code == 200
    assert _login(c, OWNER_EMAIL, TEST_PASSWORD).status_code == 401


def test_login_failure_audit_event(client):
    c, session_factory = client
    db = session_factory()
    _seed(db)
    db.close()
    assert _login(c, OWNER_EMAIL, "wrong-password-value").status_code == 401
    db = session_factory()
    from app.domain.models import AuditEvent

    events = (
        db.query(AuditEvent)
        .filter(AuditEvent.action == "LOGIN_FAILURE")
        .order_by(AuditEvent.id.desc())
        .all()
    )
    assert events
    assert "password" not in (events[0].metadata_json or "").lower()
    db.close()
