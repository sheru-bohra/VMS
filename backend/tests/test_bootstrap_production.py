"""Production bootstrap and demo-seed isolation tests."""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.application.bootstrap import (
    DEV_LOCATION_B_CODE,
    DEV_LOCATION_CODE,
    OFFICE_LOCATIONS,
    OWNER_EMAIL,
    bootstrap_application_data,
    bootstrap_development_data,
)
from app.application.seed_cleanup import DEMO_USER_EMAILS, purge_development_seed_data
from app.domain.enums import AdminRole
from app.domain.models import (
    AdminUser,
    Host,
    Location,
    VendorCompany,
    Visit,
    Visitor,
    WatchlistEntry,
)
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


def _office_codes(db) -> set[str]:
    return {code for _, code, _ in OFFICE_LOCATIONS}


def test_application_bootstrap_creates_owner_only_staff(test_db):
    TestingSessionLocal, _ = test_db
    db = TestingSessionLocal()
    bootstrap_application_data(db)

    owner = db.query(AdminUser).filter(AdminUser.email == OWNER_EMAIL).first()
    assert owner is not None
    assert owner.role == AdminRole.GLOBAL_ADMIN.value
    assert owner.is_owner is True
    assert owner.is_active is True

    staff = db.query(AdminUser).filter(AdminUser.is_owner.is_(False)).all()
    assert staff == []

    demo_count = db.query(AdminUser).filter(AdminUser.email.in_(DEMO_USER_EMAILS)).count()
    assert demo_count == 0
    db.close()


def test_application_bootstrap_creates_office_locations_not_dev_sites(test_db):
    TestingSessionLocal, _ = test_db
    db = TestingSessionLocal()
    bootstrap_application_data(db)

    codes = {loc.code for loc in db.query(Location).all()}
    assert _office_codes(db) <= codes
    assert DEV_LOCATION_CODE not in codes
    assert DEV_LOCATION_B_CODE not in codes

    for loc in db.query(Location).all():
        assert loc.is_development_seed is False
        assert loc.timezone == "Asia/Kolkata"
    db.close()


def test_application_bootstrap_leaves_operational_tables_empty(test_db):
    TestingSessionLocal, _ = test_db
    db = TestingSessionLocal()
    bootstrap_application_data(db)

    assert db.query(Visitor).count() == 0
    assert db.query(Visit).count() == 0
    assert db.query(WatchlistEntry).count() == 0
    assert db.query(VendorCompany).count() == 0
    assert db.query(Host).filter(Host.is_development_seed.is_(True)).count() == 0
    db.close()


def test_purge_removes_development_seed_then_application_bootstrap_is_clean(test_db):
    TestingSessionLocal, _ = test_db
    db = TestingSessionLocal()
    bootstrap_development_data(db)

    assert db.query(AdminUser).filter(AdminUser.email.in_(DEMO_USER_EMAILS)).count() > 0
    assert db.query(Location).filter(Location.code == DEV_LOCATION_CODE).count() == 1

    purge_development_seed_data(db)
    db.commit()
    bootstrap_application_data(db)

    assert db.query(AdminUser).filter(AdminUser.email.in_(DEMO_USER_EMAILS)).count() == 0
    assert db.query(Location).filter(Location.code.in_([DEV_LOCATION_CODE, DEV_LOCATION_B_CODE])).count() == 0
    assert db.query(AdminUser).filter(AdminUser.email == OWNER_EMAIL, AdminUser.is_owner.is_(True)).count() == 1
    assert _office_codes(db) <= {loc.code for loc in db.query(Location).all()}
    db.close()


def test_restart_does_not_recreate_demo_data(test_db):
    TestingSessionLocal, _ = test_db
    db = TestingSessionLocal()
    bootstrap_development_data(db)
    purge_development_seed_data(db)
    db.commit()

    bootstrap_application_data(db)
    bootstrap_application_data(db)

    assert db.query(AdminUser).filter(AdminUser.email.in_(DEMO_USER_EMAILS)).count() == 0
    assert db.query(Location).filter(Location.code.in_([DEV_LOCATION_CODE, DEV_LOCATION_B_CODE])).count() == 0
    db.close()


def test_empty_dashboard_kpis_after_application_bootstrap(test_db):
    TestingSessionLocal, _ = test_db
    db = TestingSessionLocal()
    bootstrap_application_data(db)
    db.close()

    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        response = client.get(
            "/api/analytics/dashboard",
            headers={"X-Dev-User-Email": OWNER_EMAIL},
        )
    assert response.status_code == 200
    kpis = response.json()["kpis"]
    assert kpis["expected_today"] == 0
    assert kpis["awaiting_approval"] == 0
    assert kpis["checked_in_today"] == 0
    assert kpis["onsite_now"] == 0
    assert kpis["checked_out_today"] == 0
    assert kpis["overstayed"] == 0
    assert kpis["vendor_contractor_onsite"] == 0


def test_development_bootstrap_still_available_for_tests(test_db):
    TestingSessionLocal, _ = test_db
    db = TestingSessionLocal()
    bootstrap_development_data(db)

    assert db.query(AdminUser).filter(AdminUser.email == "headadmin@vms.local").count() == 1
    assert db.query(Location).filter(Location.code == DEV_LOCATION_CODE).count() == 1
    db.close()
