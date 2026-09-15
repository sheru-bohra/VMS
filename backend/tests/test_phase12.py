"""Phase 12 — Entra SSO, Graph email, enterprise user access."""

import os
import tempfile
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.application.approval_service import approve_visit
from app.application.auth_service import build_auth_context
from app.application.bootstrap import bootstrap_development_data, OWNER_EMAIL
from app.application.entra_auth_service import resolve_entra_user
from app.application.entra_token_validator import validate_entra_id_token, EntraTokenError
from app.application.host_approval_service import create_host_approval_request
from app.application.invitation_service import create_advance_visit, activate_invitation
from app.application.notification_dispatch_service import dispatch_pending_notifications
from app.application.notification_templates import render_visitor_invitation_html
from app.application.registration_service import create_self_registration
from app.core.config import settings
from app.domain.enums import AdminRole, NotificationStatus, NotificationType, VisitStatus
from app.domain.models import AdminUser, Host, HostLocationAssignment, Location, Notification, UserLocationAssignment, Visit, Visitor
from app.infrastructure.database import Base, get_db
from app.main import create_app


@pytest.fixture
def rsa_keys():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_pem, public_pem


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


def _make_entra_token(private_pem: bytes, claims: dict) -> str:
    return jwt.encode(claims, private_pem, algorithm="RS256", headers={"kid": "test-key"})


def _base_claims(**overrides):
    now = datetime.now(timezone.utc)
    oid = overrides.get("oid", "test-oid-123")
    base = {
        "tid": "test-tenant-id",
        "oid": oid,
        "sub": oid,
        "aud": "vms-test-client",
        "iss": "https://login.microsoftonline.com/test-tenant-id/v2.0",
        "exp": int((now + timedelta(hours=1)).timestamp()),
        "nbf": int((now - timedelta(minutes=1)).timestamp()),
        "preferred_username": "siteadmin.blr@vms.local",
    }
    base.update(overrides)
    if "sub" not in overrides and "oid" in overrides:
        base["sub"] = overrides["oid"]
    return base


def _patch_entra_settings(monkeypatch):
    monkeypatch.setattr(settings, "auth_mode", "entra")
    monkeypatch.setattr(settings, "entra_tenant_id", "test-tenant-id")
    monkeypatch.setattr(settings, "entra_client_id", "vms-test-client")


def _mock_jwks(public_pem: bytes):
    mock_client = MagicMock()
    mock_signing_key = MagicMock()
    mock_signing_key.key = public_pem
    mock_client.get_signing_key_from_jwt.return_value = mock_signing_key
    return mock_client


def test_production_rejects_dev_auth_mode(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "auth_mode", "dev")
    monkeypatch.setattr(settings, "dev_auth_enabled", False)
    with pytest.raises(RuntimeError, match="AUTH_MODE"):
        settings.validate_environment()


def test_entra_token_validation_accepts_valid_token(monkeypatch, rsa_keys):
    private_pem, public_pem = rsa_keys
    _patch_entra_settings(monkeypatch)
    token = _make_entra_token(private_pem, _base_claims())
    with patch("app.application.entra_token_validator._get_jwks_client", return_value=_mock_jwks(public_pem)):
        claims = validate_entra_id_token(token)
    assert claims["oid"] == "test-oid-123"


def test_entra_token_wrong_tenant_rejected(monkeypatch, rsa_keys):
    private_pem, public_pem = rsa_keys
    _patch_entra_settings(monkeypatch)
    token = _make_entra_token(private_pem, _base_claims(tid="other-tenant"))
    with patch("app.application.entra_token_validator._get_jwks_client", return_value=_mock_jwks(public_pem)):
        with pytest.raises(EntraTokenError) as exc:
            validate_entra_id_token(token)
    assert exc.value.code == "AUTH_WRONG_TENANT"


def test_entra_mode_admin_api_requires_bearer(client, monkeypatch):
    c, _, _ = client
    _patch_entra_settings(monkeypatch)
    resp = c.get("/api/me")
    assert resp.status_code == 401
    body = resp.json()
    assert body["error"]["code"] == "AUTH_TOKEN_MISSING"


def test_entra_mode_ignores_dev_header(client, monkeypatch):
    c, _, _ = client
    _patch_entra_settings(monkeypatch)
    resp = c.get("/api/me", headers={"X-Dev-User-Email": OWNER_EMAIL})
    assert resp.status_code == 401


def test_first_login_links_preprovisioned_user(test_db, monkeypatch, rsa_keys):
    TestingSessionLocal, _, session = test_db
    _patch_entra_settings(monkeypatch)
    user = session.query(AdminUser).filter(AdminUser.email == "siteadmin.blr@vms.local").first()
    user.auth_provider = "entra"
    user.password_hash = None
    session.commit()
    assert user.entra_object_id is None
    claims = _base_claims(oid="linked-oid-blr", preferred_username="siteadmin.blr@vms.local")
    db = TestingSessionLocal()
    ctx = resolve_entra_user(db, claims)
    db.commit()
    db.close()
    session.expire_all()
    refreshed = session.query(AdminUser).filter(AdminUser.id == user.id).first()
    assert refreshed.entra_object_id == "linked-oid-blr"
    assert ctx.role == AdminRole.SITE_ADMIN


def test_unknown_vms_user_denied(test_db, monkeypatch):
    TestingSessionLocal, _, session = test_db
    _patch_entra_settings(monkeypatch)
    claims = _base_claims(oid="unknown-oid", preferred_username="nobody@external.com")
    db = TestingSessionLocal()
    from app.application.entra_auth_service import EntraAuthError

    with pytest.raises(EntraAuthError) as exc:
        resolve_entra_user(db, claims)
    assert exc.value.code == "VMS_USER_NOT_AUTHORIZED"


def test_inactive_user_denied(test_db, monkeypatch):
    TestingSessionLocal, _, session = test_db
    _patch_entra_settings(monkeypatch)
    user = session.query(AdminUser).filter(AdminUser.email == "security.blr@vms.local").first()
    user.is_active = False
    user.entra_tenant_id = "test-tenant-id"
    user.entra_object_id = "inactive-oid"
    session.commit()
    claims = _base_claims(oid="inactive-oid", preferred_username=user.email)
    db = TestingSessionLocal()
    from app.application.entra_auth_service import EntraAuthError

    with pytest.raises(EntraAuthError) as exc:
        resolve_entra_user(db, claims)
    assert exc.value.code == "VMS_USER_INACTIVE"


def test_owner_cannot_be_deactivated(client, monkeypatch):
    c, TestingSessionLocal, session = client
    monkeypatch.setattr(settings, "auth_mode", "dev")
    monkeypatch.setattr(settings, "dev_auth_enabled", True)
    owner = session.query(AdminUser).filter(AdminUser.email == OWNER_EMAIL).first()
    resp = c.post(
        f"/api/administration/users/{owner.id}/deactivate",
        headers={"X-Dev-User-Email": OWNER_EMAIL},
    )
    assert resp.status_code == 403


def test_global_admin_can_create_user(client, monkeypatch):
    c, TestingSessionLocal, session = client
    monkeypatch.setattr(settings, "auth_mode", "dev")
    monkeypatch.setattr(settings, "dev_auth_enabled", True)
    blr = session.query(Location).filter(Location.code == "BLR").first()
    resp = c.post(
        "/api/administration/users",
        headers={"X-Dev-User-Email": OWNER_EMAIL},
        json={
            "email": "new.admin@vms.local",
            "display_name": "New Admin",
            "role": "SITE_ADMIN",
            "location_ids": [blr.id],
            "is_active": True,
            "generate_password": True,
            "force_password_change": True,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "new.admin@vms.local"
    assert body["entra_linked"] is False


def test_site_admin_cannot_manage_users(client, monkeypatch):
    c, _, _ = client
    monkeypatch.setattr(settings, "auth_mode", "dev")
    monkeypatch.setattr(settings, "dev_auth_enabled", True)
    resp = c.get(
        "/api/administration/users",
        headers={"X-Dev-User-Email": "siteadmin.blr@vms.local"},
    )
    assert resp.status_code == 403


def test_public_registration_still_public(client, monkeypatch):
    c, _, session = client
    _patch_entra_settings(monkeypatch)
    loc = session.query(Location).filter(Location.code == "BLR").first()
    host = (
        session.query(Host)
        .join(HostLocationAssignment, HostLocationAssignment.host_id == Host.id)
        .filter(HostLocationAssignment.location_id == loc.id)
        .first()
    )
    resp = c.get(f"/api/public/sites/{loc.public_registration_token}")
    assert resp.status_code == 200
    reg = c.post(
        "/api/public/registrations",
        json={
            "site_token": loc.public_registration_token,
            "visitor_type": "BUSINESS",
            "full_name": "Public Guest",
            "mobile": "+91990001122",
            "email": "publicguest@test.com",
            "company": "Public Co",
            "host_id": host.id,
            "purpose": "Meeting",
            "expected_duration_minutes": 60,
            "policy_accepted": True,
        },
    )
    assert reg.status_code == 200


def test_visitor_invitation_email_queued_on_approval(test_db, monkeypatch):
    TestingSessionLocal, _, session = test_db
    monkeypatch.setattr(settings, "auth_mode", "dev")
    monkeypatch.setattr(settings, "dev_auth_enabled", True)
    owner = session.query(AdminUser).filter(AdminUser.email == OWNER_EMAIL).first()
    ctx = build_auth_context(owner)
    loc = session.query(Location).filter(Location.code == "BLR").first()
    host = (
        session.query(Host)
        .join(HostLocationAssignment, HostLocationAssignment.host_id == Host.id)
        .filter(HostLocationAssignment.location_id == loc.id)
        .first()
    )
    db = TestingSessionLocal()
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")
    visit = create_advance_visit(
        db,
        ctx,
        location_id=loc.id,
        host_id=host.id,
        visitor_type_code="BUSINESS",
        full_name="Invite Guest",
        mobile="9911122330",
        email="invite.guest@test.com",
        company="Invite Co",
        purpose="Workshop",
        visit_date=tomorrow,
        arrival_time="10:00",
        expected_duration_minutes=60,
    )
    approve_visit(db, ctx, visit["id"], comment="approved")
    db.commit()
    visit_row = session.query(Visit).filter(Visit.id == visit["id"]).first()
    if not visit_row.invitation_active:
        activate_invitation(db, visit_row.id)
    db.commit()
    notif = (
        session.query(Notification)
        .filter(
            Notification.visit_id == visit_row.id,
            Notification.notification_type == NotificationType.VISITOR_INVITATION.value,
        )
        .first()
    )
    assert notif is not None
    assert notif.recipient == "invite.guest@test.com"


def test_email_html_escapes_visitor_content():
    html = render_visitor_invitation_html(
        {
            "visitor_name": "<script>alert(1)</script>",
            "site_name": "Bangalore",
            "purpose": "<b>bad</b>",
            "invitation_url": "http://localhost:7272/visit/invitation/token",
        }
    )
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_entra_auth_e2e_site_admin_location_scope(client, monkeypatch, rsa_keys):
    c, TestingSessionLocal, session = client
    private_pem, public_pem = rsa_keys
    _patch_entra_settings(monkeypatch)
    user = session.query(AdminUser).filter(AdminUser.email == "siteadmin.blr@vms.local").first()
    user.entra_tenant_id = None
    user.entra_object_id = None
    user.auth_provider = "entra"
    user.password_hash = None
    user.force_password_change = False
    session.commit()
    token = _make_entra_token(
        private_pem,
        _base_claims(oid="e2e-site-admin", preferred_username="siteadmin.blr@vms.local"),
    )
    with patch("app.application.entra_token_validator._get_jwks_client", return_value=_mock_jwks(public_pem)):
        me = c.get("/api/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["role"] == "SITE_ADMIN"
    blr = session.query(Location).filter(Location.code == "BLR").first()
    mum = session.query(Location).filter(Location.code == "MUM").first()
    with patch("app.application.entra_token_validator._get_jwks_client", return_value=_mock_jwks(public_pem)):
        ok = c.get(f"/api/expected-today?site={blr.id}", headers={"Authorization": f"Bearer {token}"})
        mum = c.get(f"/api/expected-today?site={mum.id}", headers={"Authorization": f"Bearer {token}"})
    assert ok.status_code == 200
    assert mum.status_code == 200
    assert mum.json()["total"] == 0
