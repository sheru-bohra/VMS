"""Visitor photo local media storage."""

import os
import tempfile
from datetime import datetime, timedelta, timezone
from io import BytesIO

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.application.auth_service import build_auth_context
from app.application.bootstrap import bootstrap_development_data
from app.application.invitation_service import create_advance_visit
from app.application.visitor_media_filename import build_final_filename, sanitize_name_prefix
from app.application.visitor_media_service import (
    VisitorMediaError,
    finalize_visitor_photo,
    stage_visitor_photo,
)
from app.domain.models import AdminUser, HostLocationAssignment, Location, VisitorMedia
from app.infrastructure.database import Base
from app.infrastructure.local_media_storage import media_root, read_bytes


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


def _owner_ctx(session):
    user = session.query(AdminUser).filter(AdminUser.email == "sheru.bohra@lazypay.in").first()
    return build_auth_context(user)


def _tiny_jpeg() -> bytes:
    return bytes.fromhex(
        "ffd8ffe000104a46494600010100000100010000ffdb004300"
        "080606070605080707070909080a0c140d0c0b0b0c1912130f141d1a"
        "1f1e1d1a1c1c20242e2720222c231c1c2837292c30313434341f27393d"
        "38323c2e333432ffdb0043010909090c0b0c180d0d1832211c2132323232"
        "323232323232323232323232323232323232323232323232323232323232"
        "323232323232ffc00011080001000103011100021100031101ffc40014"
        "00100100000000000000000000000000000000ffc4001410010000000000"
        "0000000000000000000000ffda000c03010002110311003f00aaffd9"
    )


def test_sanitize_filename_blocks_traversal():
    assert ".." not in sanitize_name_prefix("Rohan / Sharma")
    assert "/" not in sanitize_name_prefix("bad/name")
    assert sanitize_name_prefix("Rohan Sharma") == "Rohan_Sharma"


def test_stage_and_finalize_photo(test_db):
    _, _, session = test_db
    ctx = _owner_ctx(session)
    loc = session.query(Location).filter(Location.code == "BLR").first()
    raw = _tiny_jpeg()
    staged = stage_visitor_photo(
        session,
        ctx,
        BytesIO(raw),
        "photo.jpg",
        "image/jpeg",
        len(raw),
        full_name="Test Visitor",
        source="UPLOAD",
        location_id=loc.id,
    )
    assert staged["media_id"] > 0
    row = session.get(VisitorMedia, staged["media_id"])
    assert row.status == "STAGED"
    assert row.storage_rel_path.startswith("photos/")
    data = read_bytes(row.storage_rel_path)
    assert len(data) > 0

    final = finalize_visitor_photo(
        session,
        staged["media_id"],
        visitor_id=1,
        visit_id=1,
        location_id=loc.id,
        registration_reference="VMS-BLR-000099",
        full_name="Test Visitor",
    )
    assert final is not None
    assert final["stored_filename"].startswith("Test_Visitor_VMS-BLR-000099")
    session.refresh(row)
    assert row.status == "FINALIZED"


def test_same_name_collision_unique(test_db):
    _, _, session = test_db
    ctx = _owner_ctx(session)
    loc = session.query(Location).filter(Location.code == "BLR").first()
    raw = _tiny_jpeg()
    a = stage_visitor_photo(
        session, ctx, BytesIO(raw), "a.jpg", "image/jpeg", len(raw),
        full_name="John Smith", location_id=loc.id,
    )
    b = stage_visitor_photo(
        session, ctx, BytesIO(raw), "b.jpg", "image/jpeg", len(raw),
        full_name="John Smith", location_id=loc.id,
    )
    assert a["stored_filename"] != b["stored_filename"]


def test_registration_with_photo_media_id(test_db):
    _, _, session = test_db
    ctx = _owner_ctx(session)
    loc = session.query(Location).filter(Location.code == "BLR").first()
    ha = session.query(HostLocationAssignment).filter(HostLocationAssignment.location_id == loc.id).first()
    raw = _tiny_jpeg()
    staged = stage_visitor_photo(
        session, ctx, BytesIO(raw), "p.jpg", "image/jpeg", len(raw),
        full_name="Photo Reg Visitor", location_id=loc.id,
    )
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")
    result = create_advance_visit(
        session,
        ctx,
        location_id=loc.id,
        visitor_type_code="BUSINESS",
        full_name="Photo Reg Visitor",
        mobile="9881112330",
        email="photoreg@test.com",
        company="Co",
        host_id=ha.host_id,
        visit_date=tomorrow,
        arrival_time="10:00",
        expected_duration_minutes=60,
        purpose="Meeting",
        policy_accepted=True,
        photo_media_id=staged["media_id"],
    )
    row = session.get(VisitorMedia, staged["media_id"])
    assert row.status == "FINALIZED"
    assert row.visit_id == result["id"]
    assert "Photo_Reg_Visitor" in row.stored_filename
    assert media_root().exists()
