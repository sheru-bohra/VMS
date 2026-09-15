"""Visit check-in/check-out authoritative timestamps and report wiring."""

import os
import tempfile
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.application.auth_service import build_auth_context
from app.application.bootstrap import bootstrap_development_data
from app.application.operations_service import check_in_visit, check_out_visit, mark_arrived
from app.application.report_service import REPORT_COLUMNS, list_visit_reports
from app.domain.enums import VisitStatus
from app.domain.models import AdminUser, Host, Location, Visit, Visitor, VisitorType


@pytest.fixture
def test_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    from app.infrastructure.database import Base

    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    bootstrap_development_data(db)
    yield TestingSessionLocal, db
    db.close()
    os.unlink(path)


def _create_approved_visit(session, suffix: str = "ts"):
    loc = session.query(Location).filter(Location.code == "BLR").first()
    vt = session.query(VisitorType).filter(VisitorType.code == "BUSINESS").first()
    host = session.query(Host).filter(Host.is_development_seed.is_(True)).first()
    visitor = Visitor(
        full_name=f"Timestamp Visitor {suffix}",
        email=f"ts{suffix}@test.com",
        phone=f"+9198811{suffix[:4]}",
        company="Co",
        visitor_type_id=vt.id,
    )
    session.add(visitor)
    session.flush()
    now = datetime.now(timezone.utc)
    visit = Visit(
        visitor_id=visitor.id,
        location_id=loc.id,
        status=VisitStatus.APPROVED.value,
        registration_reference=f"VMS-TS-{suffix}",
        host_id=host.id,
        host_name=host.name,
        purpose="Meeting",
        expected_duration_minutes=60,
        scheduled_start=now,
        scheduled_end=now,
        policy_accepted=True,
        source="self_registration",
    )
    session.add(visit)
    session.commit()
    session.refresh(visit)
    return visit


def _ctx(session, email: str = "sheru.bohra@lazypay.in"):
    user = session.query(AdminUser).filter(AdminUser.email == email).first()
    return build_auth_context(user)


def test_check_in_sets_checked_in_at(test_db):
    TestingSessionLocal, session = test_db
    visit = _create_approved_visit(session, "in")
    db = TestingSessionLocal()
    ctx = _ctx(session)
    mark_arrived(db, ctx, visit.id)
    db.commit()
    result = check_in_visit(db, ctx, visit.id)
    db.commit()
    assert result["status"] == VisitStatus.ONSITE.value
    assert result["checked_in_at"] is not None
    refreshed = db.query(Visit).filter(Visit.id == visit.id).first()
    assert refreshed.checked_in_at is not None
    assert refreshed.checked_out_at is None
    db.close()


def test_check_out_sets_checked_out_at(test_db):
    TestingSessionLocal, session = test_db
    visit = _create_approved_visit(session, "out")
    db = TestingSessionLocal()
    ctx = _ctx(session)
    mark_arrived(db, ctx, visit.id)
    check_in_visit(db, ctx, visit.id)
    db.commit()
    result = check_out_visit(db, ctx, visit.id)
    db.commit()
    assert result["status"] == VisitStatus.CHECKED_OUT.value
    assert result["checked_out_at"] is not None
    refreshed = db.query(Visit).filter(Visit.id == visit.id).first()
    assert refreshed.checked_in_at is not None
    assert refreshed.checked_out_at is not None
    db.close()


def test_double_check_in_preserves_checked_in_at(test_db):
    TestingSessionLocal, session = test_db
    visit = _create_approved_visit(session, "dupin")
    db = TestingSessionLocal()
    ctx = _ctx(session)
    mark_arrived(db, ctx, visit.id)
    first = check_in_visit(db, ctx, visit.id)
    db.commit()
    first_ts = first["checked_in_at"]
    second = check_in_visit(db, ctx, visit.id)
    db.commit()
    assert second["checked_in_at"] == first_ts
    db.close()


def test_double_check_out_preserves_checked_out_at(test_db):
    TestingSessionLocal, session = test_db
    visit = _create_approved_visit(session, "dupout")
    db = TestingSessionLocal()
    ctx = _ctx(session)
    mark_arrived(db, ctx, visit.id)
    check_in_visit(db, ctx, visit.id)
    db.commit()
    first = check_out_visit(db, ctx, visit.id)
    db.commit()
    first_ts = first["checked_out_at"]
    second = check_out_visit(db, ctx, visit.id)
    db.commit()
    assert second["checked_out_at"] == first_ts
    db.close()


def test_report_columns_include_visit_timestamps(test_db):
    column_keys = [key for key, _ in REPORT_COLUMNS]
    assert "scheduled_start" in column_keys
    assert "scheduled_end" in column_keys
    assert "checked_in_at" in column_keys
    assert "checked_out_at" in column_keys
    assert "visit_duration_minutes" in column_keys


def test_report_rows_include_timestamp_fields(test_db):
    TestingSessionLocal, session = test_db
    visit = _create_approved_visit(session, "rep")
    db = TestingSessionLocal()
    ctx = _ctx(session)
    mark_arrived(db, ctx, visit.id)
    check_in_visit(db, ctx, visit.id)
    db.commit()
    now = datetime.now(timezone.utc)
    rows, total = list_visit_reports(
        db,
        ctx,
        from_dt=now - timedelta(days=1),
        to_dt=now + timedelta(days=1),
    )
    assert total >= 1
    row = next(r for r in rows if r["registration_reference"] == visit.registration_reference)
    assert row["checked_in_at"] is not None
    assert row["scheduled_start"] is not None
    assert row["scheduled_end"] is not None
    db.close()
