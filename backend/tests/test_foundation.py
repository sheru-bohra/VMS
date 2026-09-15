import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.domain.enums import AdminRole, Permission, get_permissions_for_role, role_has_permission
from app.domain.visit_state import can_transition, validate_transition, VisitStateError
from app.domain.enums import VisitStatus
from app.infrastructure.database import Base, get_db
from app.main import create_app
from app.application.bootstrap import OWNER_EMAIL, ensure_owner_protected
from app.domain.models import AdminUser


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


def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "vms-api"


def test_default_owner_bootstrap(test_db):
    TestingSessionLocal, _ = test_db
    db = TestingSessionLocal()
    from app.application.bootstrap import bootstrap_development_data
    bootstrap_development_data(db)
    owner = db.query(AdminUser).filter(AdminUser.email == OWNER_EMAIL).first()
    assert owner is not None
    assert owner.role == AdminRole.GLOBAL_ADMIN.value
    assert owner.is_owner is True
    assert owner.is_active is True
    db.close()


def test_global_admin_has_full_permissions():
    perms = get_permissions_for_role(AdminRole.GLOBAL_ADMIN)
    assert Permission.REPORTS_EXPORT in perms
    assert Permission.ANALYTICS_WEEKLY_VIEW in perms
    assert Permission.ADMINS_MANAGE in perms


def test_head_admin_has_report_export():
    perms = get_permissions_for_role(AdminRole.HEAD_ADMIN)
    assert Permission.REPORTS_EXPORT in perms
    assert Permission.ANALYTICS_WEEKLY_VIEW in perms
    assert Permission.ANALYTICS_MONTHLY_VIEW in perms


def test_site_admin_no_report_permissions():
    perms = get_permissions_for_role(AdminRole.SITE_ADMIN)
    assert Permission.REPORTS_EXPORT not in perms
    assert Permission.REPORTS_VIEW not in perms
    assert Permission.ANALYTICS_WEEKLY_VIEW not in perms
    assert Permission.ANALYTICS_MONTHLY_VIEW not in perms
    assert Permission.ANALYTICS_DASHBOARD_VIEW not in perms


def test_site_admin_has_operational_permissions():
    perms = get_permissions_for_role(AdminRole.SITE_ADMIN)
    assert Permission.VISITOR_READ in perms
    assert Permission.VISITOR_CHECKIN in perms
    assert Permission.ONSITE_READ in perms


def test_visit_state_rejects_illegal_transition():
    assert not can_transition(VisitStatus.REJECTED, VisitStatus.CHECKED_IN)
    with pytest.raises(VisitStateError):
        validate_transition(VisitStatus.REJECTED, VisitStatus.CHECKED_IN)


def test_visit_state_allows_valid_transition():
    assert can_transition(VisitStatus.APPROVED, VisitStatus.ARRIVED)
    validate_transition(VisitStatus.APPROVED, VisitStatus.ARRIVED)


def test_production_rejects_dev_auth():
    original_env = settings.app_env
    original_dev = settings.dev_auth_enabled
    settings.app_env = "production"
    settings.dev_auth_enabled = True
    try:
        with pytest.raises(RuntimeError, match="DEV_AUTH_ENABLED cannot be true"):
            settings.validate_environment()
    finally:
        settings.app_env = original_env
        settings.dev_auth_enabled = original_dev


def test_owner_protection():
    owner = AdminUser(email=OWNER_EMAIL, role=AdminRole.GLOBAL_ADMIN.value, is_owner=True, is_active=True)
    with pytest.raises(ValueError, match="Cannot deactivate"):
        ensure_owner_protected(owner, {"is_active": False})
    with pytest.raises(ValueError, match="Cannot downgrade"):
        ensure_owner_protected(owner, {"role": AdminRole.SITE_ADMIN.value})
