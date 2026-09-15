"""Microsoft Entra SSO-only authentication and VMS authorization tests."""

import os
import tempfile
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.application.entra_auth_service import EntraAuthError, resolve_entra_user
from app.application.entra_token_validator import EntraTokenError, validate_entra_id_token
from app.core.config import settings
from app.domain.enums import AdminRole
from app.domain.models import AdminUser
from app.infrastructure.database import Base


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
def empty_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    yield TestingSessionLocal, db
    db.close()
    os.unlink(path)


def _patch_entra(monkeypatch):
    monkeypatch.setattr(settings, "entra_tenant_id", "corp-tenant")
    monkeypatch.setattr(settings, "entra_client_id", "spa-client-id")
    monkeypatch.setattr(settings, "vms_bootstrap_admin_email", "bootstrap@company.com")


def _make_token(private_pem: bytes, **overrides) -> str:
    now = datetime.now(timezone.utc)
    oid = overrides.get("oid", "oid-1")
    claims = {
        "tid": "corp-tenant",
        "oid": oid,
        "sub": oid,
        "aud": "spa-client-id",
        "iss": "https://login.microsoftonline.com/corp-tenant/v2.0",
        "exp": int((now + timedelta(hours=1)).timestamp()),
        "nbf": int((now - timedelta(minutes=1)).timestamp()),
        "preferred_username": overrides.get("preferred_username", "user@company.com"),
        "name": overrides.get("name", "Test User"),
    }
    claims.update(overrides)
    return jwt.encode(claims, private_pem, algorithm="RS256", headers={"kid": "test-key"})


def _mock_jwks(public_pem: bytes):
    mock_client = MagicMock()
    mock_signing_key = MagicMock()
    mock_signing_key.key = public_pem
    mock_client.get_signing_key_from_jwt.return_value = mock_signing_key
    return mock_client


def test_bootstrap_global_admin_on_first_login(empty_db, monkeypatch, rsa_keys):
    TestingSessionLocal, _ = empty_db
    _patch_entra(monkeypatch)
    private_pem, public_pem = rsa_keys
    token = _make_token(private_pem, oid="bootstrap-oid", preferred_username="bootstrap@company.com")
    with patch("app.application.entra_token_validator._get_jwks_client", return_value=_mock_jwks(public_pem)):
        claims = validate_entra_id_token(token)
    db = TestingSessionLocal()
    ctx = resolve_entra_user(db, claims)
    db.commit()
    user = db.query(AdminUser).filter(AdminUser.email == "bootstrap@company.com").first()
    assert user is not None
    assert user.role == AdminRole.GLOBAL_ADMIN.value
    assert user.entra_object_id == "bootstrap-oid"
    assert ctx.role == AdminRole.GLOBAL_ADMIN
    db.close()


def test_bootstrap_not_repeated_when_global_admin_exists(empty_db, monkeypatch, rsa_keys):
    TestingSessionLocal, session = empty_db
    _patch_entra(monkeypatch)
    session.add(
        AdminUser(
            email="existing@company.com",
            role=AdminRole.GLOBAL_ADMIN.value,
            is_owner=True,
            is_active=True,
        )
    )
    session.commit()
    private_pem, public_pem = rsa_keys
    token = _make_token(private_pem, oid="other-oid", preferred_username="bootstrap@company.com")
    with patch("app.application.entra_token_validator._get_jwks_client", return_value=_mock_jwks(public_pem)):
        claims = validate_entra_id_token(token)
    db = TestingSessionLocal()
    with pytest.raises(EntraAuthError) as exc:
        resolve_entra_user(db, claims)
    assert exc.value.code == "VMS_USER_NOT_AUTHORIZED"
    assert db.query(AdminUser).filter(AdminUser.email == "bootstrap@company.com").count() == 0
    db.close()


def test_returning_user_identified_by_oid_not_email(empty_db, monkeypatch, rsa_keys):
    TestingSessionLocal, session = empty_db
    _patch_entra(monkeypatch)
    user = AdminUser(
        email="john@company.com",
        role=AdminRole.SITE_ADMIN.value,
        is_active=True,
        entra_tenant_id="corp-tenant",
        entra_object_id="john-oid",
        auth_provider="entra",
    )
    session.add(user)
    session.commit()
    private_pem, public_pem = rsa_keys
    token = _make_token(
        private_pem,
        oid="john-oid",
        preferred_username="john.newemail@company.com",
    )
    with patch("app.application.entra_token_validator._get_jwks_client", return_value=_mock_jwks(public_pem)):
        claims = validate_entra_id_token(token)
    db = TestingSessionLocal()
    ctx = resolve_entra_user(db, claims)
    assert ctx.email == "john@company.com"
    db.close()


def test_invalid_audience_rejected(monkeypatch, rsa_keys):
    private_pem, public_pem = rsa_keys
    _patch_entra(monkeypatch)
    token = _make_token(private_pem, aud="wrong-audience")
    with patch("app.application.entra_token_validator._get_jwks_client", return_value=_mock_jwks(public_pem)):
        with pytest.raises(EntraTokenError):
            validate_entra_id_token(token)


def test_expired_token_rejected(monkeypatch, rsa_keys):
    private_pem, public_pem = rsa_keys
    _patch_entra(monkeypatch)
    now = datetime.now(timezone.utc)
    token = _make_token(
        private_pem,
        exp=int((now - timedelta(hours=1)).timestamp()),
    )
    with patch("app.application.entra_token_validator._get_jwks_client", return_value=_mock_jwks(public_pem)):
        with pytest.raises(EntraTokenError) as exc:
            validate_entra_id_token(token)
    assert exc.value.code == "AUTH_TOKEN_INVALID"


def test_graph_not_used_in_email_provider(monkeypatch):
    from app.application.email_provider import get_email_provider

    monkeypatch.setattr(settings, "email_provider", "ms_graph")
    with pytest.raises(RuntimeError, match="ms_graph"):
        get_email_provider()
