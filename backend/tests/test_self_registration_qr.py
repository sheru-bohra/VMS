"""Tests for permanent reception self-registration QR."""

import os
import tempfile
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.application.bootstrap import bootstrap_development_data
from app.application.registration_url_service import build_registration_public_url
from app.application.self_registration_qr_service import (
    SelfRegistrationQrError,
    get_self_registration_qr_config,
)
from app.application.auth_service import build_auth_context
from app.core.config import settings
from app.domain.enums import VisitStatus
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


def _owner_ctx(session):
    owner = session.query(AdminUser).filter(AdminUser.email == "sheru.bohra@lazypay.in").first()
    return build_auth_context(owner)


def _create_self_reg(session, loc: Location, suffix: str, status: str):
    vt = session.query(VisitorType).filter(VisitorType.code == "BUSINESS").first()
    host = session.query(Host).filter(Host.is_development_seed.is_(True)).first()
    visitor = Visitor(
        full_name=f"QR Visitor {suffix}",
        email=f"qr{suffix}@test.com",
        phone=f"+9199000{suffix[:4]}",
        company="Co",
        visitor_type_id=vt.id,
    )
    session.add(visitor)
    session.flush()
    visit = Visit(
        visitor_id=visitor.id,
        location_id=loc.id,
        status=status,
        registration_reference=f"VMS-QR-{suffix}",
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
    return visit


def test_build_registration_url_uses_public_base(monkeypatch):
    monkeypatch.setattr(settings, "public_app_base_url", "https://vms.example.com")
    url = build_registration_public_url("opaque-token-abc")
    assert url == "https://vms.example.com/visit/register/opaque-token-abc"
    assert "localhost" not in url


def test_permanent_token_stable_across_reads(test_db, monkeypatch):
    TestingSessionLocal, session = test_db
    monkeypatch.setattr(settings, "public_app_base_url", "https://vms.example.com")
    loc = session.query(Location).filter(Location.code == "BLR").first()
    token_first = loc.public_registration_token
    db = TestingSessionLocal()
    ctx = _owner_ctx(session)
    cfg1 = get_self_registration_qr_config(db, ctx, location_id=loc.id)
    cfg2 = get_self_registration_qr_config(db, ctx, location_id=loc.id)
    db.close()
    session.refresh(loc)
    assert loc.public_registration_token == token_first
    assert cfg1["registration_url"] == cfg2["registration_url"]


def test_location_specific_tokens_differ(test_db, monkeypatch):
    TestingSessionLocal, session = test_db
    monkeypatch.setattr(settings, "public_app_base_url", "https://vms.example.com")
    blr = session.query(Location).filter(Location.code == "BLR").first()
    mum = session.query(Location).filter(Location.code == "MUM").first()
    db = TestingSessionLocal()
    ctx = _owner_ctx(session)
    blr_cfg = get_self_registration_qr_config(db, ctx, location_id=blr.id)
    mum_cfg = get_self_registration_qr_config(db, ctx, location_id=mum.id)
    db.close()
    assert blr_cfg["registration_url"] != mum_cfg["registration_url"]


def test_site_admin_cannot_access_other_location_qr(test_db, monkeypatch):
    TestingSessionLocal, session = test_db
    monkeypatch.setattr(settings, "public_app_base_url", "https://vms.example.com")
    mum = session.query(Location).filter(Location.code == "MUM").first()
    site_admin = session.query(AdminUser).filter(AdminUser.email == "siteadmin.blr@vms.local").first()
    ctx = build_auth_context(site_admin)
    db = TestingSessionLocal()
    with pytest.raises(SelfRegistrationQrError) as exc:
        get_self_registration_qr_config(db, ctx, location_id=mum.id)
    assert exc.value.status_code == 403
    db.close()


def test_qr_config_stats_today(test_db, monkeypatch):
    TestingSessionLocal, session = test_db
    monkeypatch.setattr(settings, "public_app_base_url", "https://vms.example.com")
    loc = session.query(Location).filter(Location.code == "BLR").first()
    _create_self_reg(session, loc, "pend", VisitStatus.PENDING_APPROVAL.value)
    _create_self_reg(session, loc, "appr", VisitStatus.APPROVED.value)
    db = TestingSessionLocal()
    ctx = _owner_ctx(session)
    cfg = get_self_registration_qr_config(db, ctx, location_id=loc.id)
    assert cfg["stats"]["today"] >= 2
    assert cfg["stats"]["pending"] >= 1
    assert cfg["stats"]["approved"] >= 1
    db.close()


def test_qr_config_api_requires_auth(client, monkeypatch):
    c, _, _ = client
    monkeypatch.setattr(settings, "auth_mode", "entra")
    resp = c.get("/api/self-registrations/qr-config")
    assert resp.status_code == 401


def test_qr_config_api_dev_mode(client, monkeypatch):
    c, _, session = client
    monkeypatch.setattr(settings, "auth_mode", "dev")
    monkeypatch.setattr(settings, "dev_auth_enabled", True)
    monkeypatch.setattr(settings, "public_app_base_url", "http://localhost:7272")
    blr = session.query(Location).filter(Location.code == "BLR").first()
    resp = c.get(
        f"/api/self-registrations/qr-config?site={blr.id}",
        headers={"X-Dev-User-Email": "sheru.bohra@lazypay.in"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["registration_url"].endswith(f"/visit/register/{blr.public_registration_token}")
    assert body["is_permanent"] is True
    assert body["localhost_warning"] is True
