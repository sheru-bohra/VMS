"""Dashboard visitor activity buckets and KPI reconciliation."""

import os
import tempfile
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.application.analytics_service import get_dashboard
from app.application.auth_service import build_auth_context
from app.application.bootstrap import bootstrap_development_data
from app.domain.enums import VisitStatus
from app.domain.models import AdminUser, Visit
from app.infrastructure.database import Base
from tests.test_phase4 import _create_approved_visit


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


def _ctx(session, email: str):
    user = session.query(AdminUser).filter(AdminUser.email == email).first()
    return build_auth_context(user)


def test_today_visitor_trend_uses_hourly_buckets(test_db):
    _, _, session = test_db
    owner = _ctx(session, "sheru.bohra@lazypay.in")
    data = get_dashboard(session, owner, period="today")
    trend = data["visitor_trend"]
    assert len(trend) == 24
    assert trend[0]["granularity"] == "hour"
    assert trend[0]["label"] == "00:00"
    assert "checked_in" in trend[0]


def test_last_7_days_visitor_trend_uses_daily_buckets(test_db):
    _, _, session = test_db
    owner = _ctx(session, "sheru.bohra@lazypay.in")
    data = get_dashboard(session, owner, period="last_7_days")
    trend = data["visitor_trend"]
    assert len(trend) >= 1
    assert trend[0]["granularity"] == "day"
    assert trend[0]["label"]


def test_kpi_awaiting_approval_counts_pending_only(test_db):
    _, _, session = test_db
    owner = _ctx(session, "sheru.bohra@lazypay.in")
    _create_approved_visit(session, "BLR", "kpi-pending-1")
    visit = session.query(Visit).filter(Visit.registration_reference.like("%kpi-pending%")).first()
    visit.status = VisitStatus.PENDING_APPROVAL.value
    session.commit()
    data = get_dashboard(session, owner, period="today")
    assert data["kpis"]["awaiting_approval"] >= 1


def test_location_performance_excludes_development_seed_locations(test_db):
    _, _, session = test_db
    owner = _ctx(session, "sheru.bohra@lazypay.in")
    data = get_dashboard(session, owner, period="today")
    names = [row["location_name"] for row in data["locations"]]
    assert "Development Main Office" not in names
    assert "Development Site B" not in names
