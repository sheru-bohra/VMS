"""Regression tests for permanent owner email migration (payu.in → lazypay.in)."""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.application.admin_user_service import AdminUserError, deactivate_admin_user, update_admin_user
from app.application.auth_service import build_auth_context
from app.application.bootstrap import (
    LEGACY_OWNER_EMAIL,
    OWNER_EMAIL,
    OwnerEmailConflictError,
    bootstrap_development_data,
    ensure_owner_protected,
    is_owner_email,
    reconcile_owner_identity,
)
from app.domain.enums import AdminRole
from app.domain.models import AdminUser, AuditEvent, Location, UserLocationAssignment
from app.infrastructure.database import Base, get_db
from app.main import create_app


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
def client(test_db):
    TestingSessionLocal, _ = test_db

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _legacy_owner(db, **kwargs):
    owner = AdminUser(
        email=LEGACY_OWNER_EMAIL,
        display_name="Sheru Bohra",
        role=AdminRole.GLOBAL_ADMIN.value,
        is_owner=True,
        is_active=True,
        **kwargs,
    )
    db.add(owner)
    db.flush()
    return owner


def test_bootstrap_creates_lazypay_owner_on_clean_db(test_db):
    TestingSessionLocal, _ = test_db
    db = TestingSessionLocal()
    bootstrap_development_data(db)
    owner = db.query(AdminUser).filter(AdminUser.email == OWNER_EMAIL).first()
    assert owner is not None
    assert owner.role == AdminRole.GLOBAL_ADMIN.value
    assert owner.is_owner is True
    assert owner.is_active is True
    legacy_count = db.query(AdminUser).filter(AdminUser.email == LEGACY_OWNER_EMAIL).count()
    assert legacy_count == 0
    owners = db.query(AdminUser).filter(AdminUser.is_owner.is_(True)).all()
    assert len(owners) == 1
    db.close()


def test_migrate_legacy_owner_preserves_primary_key_and_metadata(test_db):
    TestingSessionLocal, _ = test_db
    db = TestingSessionLocal()
    owner = _legacy_owner(db, entra_tenant_id="tenant-1", entra_object_id="object-1")
    owner_id = owner.id
    loc = Location(name="Test", code="TST", city="Test", timezone="Asia/Kolkata", is_active=True)
    db.add(loc)
    db.flush()
    db.add(UserLocationAssignment(admin_user_id=owner_id, location_id=loc.id))
    db.commit()

    migrated = reconcile_owner_identity(db)
    db.commit()

    assert migrated is not None
    assert migrated.id == owner_id
    assert migrated.email == OWNER_EMAIL
    assert migrated.role == AdminRole.GLOBAL_ADMIN.value
    assert migrated.is_owner is True
    assert migrated.is_active is True
    assert migrated.entra_tenant_id == "tenant-1"
    assert migrated.entra_object_id == "object-1"
    assert len(migrated.location_assignments) == 1
    assert migrated.location_assignments[0].location_id == loc.id

    audit = (
        db.query(AuditEvent)
        .filter(AuditEvent.action == "OWNER_EMAIL_UPDATED", AuditEvent.entity_id == str(owner_id))
        .first()
    )
    assert audit is not None
    assert LEGACY_OWNER_EMAIL in (audit.before_value or "")
    assert OWNER_EMAIL in (audit.after_value or "")
    db.close()


def test_bootstrap_twice_is_idempotent(test_db):
    TestingSessionLocal, _ = test_db
    db = TestingSessionLocal()
    bootstrap_development_data(db)
    first_id = db.query(AdminUser).filter(AdminUser.email == OWNER_EMAIL).first().id
    bootstrap_development_data(db)
    owner = db.query(AdminUser).filter(AdminUser.email == OWNER_EMAIL).first()
    assert owner.id == first_id
    assert db.query(AdminUser).filter(AdminUser.is_owner.is_(True)).count() == 1
    db.close()


def test_legacy_email_no_longer_recognized_as_owner():
    assert is_owner_email(LEGACY_OWNER_EMAIL) is False
    assert is_owner_email(OWNER_EMAIL) is True


def test_owner_email_conflict_when_both_accounts_exist(test_db):
    TestingSessionLocal, _ = test_db
    db = TestingSessionLocal()
    _legacy_owner(db)
    db.add(
        AdminUser(
            email=OWNER_EMAIL,
            role=AdminRole.GLOBAL_ADMIN.value,
            is_owner=True,
            is_active=True,
        )
    )
    db.commit()
    with pytest.raises(OwnerEmailConflictError, match="OWNER_EMAIL_CONFLICT"):
        reconcile_owner_identity(db)
    db.close()


def test_owner_protection_deactivate_downgrade_delete(test_db):
    TestingSessionLocal, _ = test_db
    db = TestingSessionLocal()
    bootstrap_development_data(db)
    owner = db.query(AdminUser).filter(AdminUser.email == OWNER_EMAIL).first()
    ctx = build_auth_context(owner)

    with pytest.raises(AdminUserError, match="deactivated"):
        deactivate_admin_user(db, ctx, owner.id)

    with pytest.raises(AdminUserError, match="role cannot be changed"):
        update_admin_user(db, ctx, owner.id, role=AdminRole.HEAD_ADMIN.value)

    with pytest.raises(ValueError, match="Cannot deactivate"):
        ensure_owner_protected(owner, {"is_active": False})

    with pytest.raises(ValueError, match="Cannot downgrade"):
        ensure_owner_protected(owner, {"role": AdminRole.SECURITY.value})

    with pytest.raises(ValueError, match="Cannot remove owner"):
        ensure_owner_protected(owner, {"is_owner": False})
    db.close()


def test_dev_auth_me_returns_lazypay_owner(client, test_db):
    TestingSessionLocal, _ = test_db
    db = TestingSessionLocal()
    bootstrap_development_data(db)
    db.close()

    response = client.get("/api/me", headers={"X-Dev-User-Email": OWNER_EMAIL})
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == OWNER_EMAIL
    assert data["role"] == AdminRole.GLOBAL_ADMIN.value
    assert data["is_owner"] is True

    legacy = client.get("/api/me", headers={"X-Dev-User-Email": LEGACY_OWNER_EMAIL})
    assert legacy.status_code in (401, 403, 404)
