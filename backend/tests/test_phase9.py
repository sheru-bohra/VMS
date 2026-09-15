"""Phase 9: Emergency / evacuation visitor roll-call."""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.application.auth_service import build_auth_context
from app.application.bootstrap import bootstrap_development_data
from app.application.emergency_roll_call_service import (
    EmergencyRollCallError,
    close_emergency,
    get_emergency,
    list_roll_call,
    start_emergency,
    update_roll_call_status,
)
from app.application.operations_service import check_in_visit, check_out_visit, mark_arrived, OperationsError
from app.domain.enums import RollCallEntryStatus, VisitStatus
from app.domain.models import AdminUser, EmergencyEvent, EmergencyRollCallAction, Location, Visit
from app.infrastructure.database import Base, get_db
from app.main import create_app

PDF_BYTES = b"%PDF-1.4\n"


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


def _ctx(session, email: str):
    user = session.query(AdminUser).filter(AdminUser.email == email).first()
    return build_auth_context(user)


def _onsite_visit(session, suffix: str, location_code: str = "BLR"):
    from tests.test_phase4 import _create_approved_visit
    from app.application.security_screening_service import screen_visit
    from app.application.security_review_service import resolve_clear
    from app.domain.enums import SecurityClearanceStatus
    visit, loc = _create_approved_visit(session, location_code, suffix)
    owner = _ctx(session, "sheru.bohra@lazypay.in")
    sec = _ctx(session, "security.blr@vms.local")
    mark_arrived(session, owner, visit.id)
    screen_visit(session, visit.id, trigger="check_in")
    session.refresh(visit)
    if visit.security_clearance_status == SecurityClearanceStatus.REVIEW.value:
        resolve_clear(session, sec, visit.id, comment="cleared for emergency test")
    check_in_visit(session, owner, visit.id)
    session.commit()
    session.refresh(visit)
    return visit, loc


def test_security_can_start_own_site_emergency(test_db):
    _, _, session = test_db
    visit, loc = _onsite_visit(session, "secstart")
    sec = _ctx(session, "security.blr@vms.local")
    detail = start_emergency(session, sec, loc.id, "EVACUATION_DRILL")
    assert detail["status"] == "ACTIVE"
    assert detail["visitor_snapshot_count"] >= 1


def test_global_admin_can_start_any_site(test_db):
    _, _, session = test_db
    mum = session.query(Location).filter(Location.code == "MUM").first()
    owner = _ctx(session, "sheru.bohra@lazypay.in")
    detail = start_emergency(session, owner, mum.id, "EMERGENCY")
    assert detail["location_id"] == mum.id


def test_security_cannot_start_mumbai_emergency(test_db):
    _, _, session = test_db
    mum = session.query(Location).filter(Location.code == "MUM").first()
    sec = _ctx(session, "security.blr@vms.local")
    with pytest.raises(EmergencyRollCallError) as exc:
        start_emergency(session, sec, mum.id, "EMERGENCY")
    assert exc.value.status_code == 403


def test_snapshot_includes_only_onsite(test_db):
    _, _, session = test_db
    onsite, loc = _onsite_visit(session, "snap1")
    from tests.test_phase4 import _create_approved_visit
    approved_only, _ = _create_approved_visit(session, "BLR", "approvedonly")
    owner = _ctx(session, "sheru.bohra@lazypay.in")
    event = start_emergency(session, owner, loc.id, "EMERGENCY")
    entries = list_roll_call(session, owner, event["id"])
    visit_ids = {e["visit_id"] for e in entries}
    assert onsite.id in visit_ids
    assert approved_only.id not in visit_ids


def test_zero_visitor_emergency_allowed(test_db):
    _, _, session = test_db
    pun = session.query(Location).filter(Location.code == "PUN").first()
    owner = _ctx(session, "sheru.bohra@lazypay.in")
    detail = start_emergency(session, owner, pun.id, "EVACUATION_DRILL")
    assert detail["visitor_snapshot_count"] == 0
    assert detail["counts"]["total"] == 0


def test_duplicate_active_emergency_blocked(test_db):
    _, _, session = test_db
    _, loc = _onsite_visit(session, "dup1")
    owner = _ctx(session, "sheru.bohra@lazypay.in")
    start_emergency(session, owner, loc.id, "EMERGENCY")
    with pytest.raises(EmergencyRollCallError) as exc:
        start_emergency(session, owner, loc.id, "EMERGENCY")
    assert exc.value.code == "EMERGENCY_ALREADY_ACTIVE"
    assert exc.value.status_code == 409


def test_roll_call_status_updates_and_history(test_db):
    _, _, session = test_db
    visit, loc = _onsite_visit(session, "status1")
    owner = _ctx(session, "sheru.bohra@lazypay.in")
    event = start_emergency(session, owner, loc.id, "EMERGENCY")
    entries = list_roll_call(session, owner, event["id"])
    entry = entries[0]
    assert entry["status"] == RollCallEntryStatus.UNACCOUNTED.value
    updated = update_roll_call_status(session, owner, event["id"], entry["id"], RollCallEntryStatus.NOT_LOCATED.value)
    assert updated["status"] == RollCallEntryStatus.NOT_LOCATED.value
    updated2 = update_roll_call_status(session, owner, event["id"], entry["id"], RollCallEntryStatus.SAFE.value)
    assert updated2["status"] == RollCallEntryStatus.SAFE.value
    actions = session.query(EmergencyRollCallAction).filter(EmergencyRollCallAction.roll_call_entry_id == entry["id"]).all()
    assert len(actions) >= 2


def test_closed_event_cannot_be_edited(test_db):
    _, _, session = test_db
    visit, loc = _onsite_visit(session, "closed1")
    owner = _ctx(session, "sheru.bohra@lazypay.in")
    event = start_emergency(session, owner, loc.id, "EMERGENCY")
    entries = list_roll_call(session, owner, event["id"])
    close_emergency(session, owner, event["id"], confirm_unresolved=True, closure_comment="Drill complete")
    with pytest.raises(EmergencyRollCallError) as exc:
        update_roll_call_status(session, owner, event["id"], entries[0]["id"], RollCallEntryStatus.SAFE.value)
    assert exc.value.status_code == 409


def test_checkin_blocked_during_active_emergency(test_db):
    TestingSessionLocal, _, session = test_db
    _, loc = _onsite_visit(session, "gate1")
    owner = _ctx(session, "sheru.bohra@lazypay.in")
    start_emergency(session, owner, loc.id, "EMERGENCY")
    from tests.test_phase4 import _create_approved_visit
    from app.application.security_screening_service import screen_visit
    from app.application.security_review_service import resolve_clear
    from app.domain.enums import SecurityClearanceStatus
    new_visit, _ = _create_approved_visit(session, "BLR", "gate2")
    new_visit_id = new_visit.id
    sec = _ctx(session, "security.blr@vms.local")
    db = TestingSessionLocal()
    mark_arrived(db, sec, new_visit_id)
    screen_visit(db, new_visit_id, trigger="check_in")
    gate_visit = db.get(Visit, new_visit_id)
    if gate_visit and gate_visit.security_clearance_status == SecurityClearanceStatus.REVIEW.value:
        resolve_clear(db, sec, new_visit_id, comment="clear")
    with pytest.raises(OperationsError) as exc:
        check_in_visit(db, sec, new_visit_id)
    assert exc.value.code == "LOCATION_EMERGENCY_ACTIVE"


def test_checkout_allowed_during_emergency(test_db):
    TestingSessionLocal, _, session = test_db
    visit, loc = _onsite_visit(session, "co1")
    owner = _ctx(session, "sheru.bohra@lazypay.in")
    event = start_emergency(session, owner, loc.id, "EMERGENCY")
    sec = _ctx(session, "security.blr@vms.local")
    db = TestingSessionLocal()
    check_out_visit(db, sec, visit.id)
    entries = list_roll_call(session, owner, event["id"])
    matched = [e for e in entries if e["visit_id"] == visit.id]
    assert len(matched) == 1
    assert matched[0]["visit_checked_out_after_start"] is True


def test_snapshot_immutable_after_visitor_change(test_db):
    _, _, session = test_db
    visit, loc = _onsite_visit(session, "immut1")
    owner = _ctx(session, "sheru.bohra@lazypay.in")
    event = start_emergency(session, owner, loc.id, "EMERGENCY")
    entries = list_roll_call(session, owner, event["id"])
    original_name = entries[0]["visitor_name"]
    visit.visitor.full_name = "Changed Name Forever"
    session.commit()
    entries2 = list_roll_call(session, owner, event["id"])
    assert entries2[0]["visitor_name"] == original_name


def test_close_with_unresolved_requires_confirmation(test_db):
    _, _, session = test_db
    _, loc = _onsite_visit(session, "unres1")
    owner = _ctx(session, "sheru.bohra@lazypay.in")
    event = start_emergency(session, owner, loc.id, "EMERGENCY")
    with pytest.raises(EmergencyRollCallError) as exc:
        close_emergency(session, owner, event["id"])
    assert exc.value.code == "unresolved_visitors"
    closed = close_emergency(session, owner, event["id"], closure_comment="Drill ended", confirm_unresolved=True)
    assert closed["status"] == "CLOSED"


def test_checkin_reopens_after_close(test_db):
    TestingSessionLocal, _, session = test_db
    _, loc = _onsite_visit(session, "reopen1")
    owner = _ctx(session, "sheru.bohra@lazypay.in")
    event = start_emergency(session, owner, loc.id, "EMERGENCY")
    close_emergency(session, owner, event["id"], confirm_unresolved=True, closure_comment="All clear")
    from tests.test_phase4 import _create_approved_visit
    from app.application.security_screening_service import screen_visit
    from app.application.security_review_service import resolve_clear
    from app.domain.enums import SecurityClearanceStatus
    new_visit, _ = _create_approved_visit(session, "BLR", "reopen2")
    new_visit_id = new_visit.id
    sec = _ctx(session, "security.blr@vms.local")
    db = TestingSessionLocal()
    mark_arrived(db, sec, new_visit_id)
    screen_visit(db, new_visit_id, trigger="check_in")
    reopen_gate = db.get(Visit, new_visit_id)
    if reopen_gate and reopen_gate.security_clearance_status == SecurityClearanceStatus.REVIEW.value:
        resolve_clear(db, sec, new_visit_id, comment="clear")
    check_in_visit(db, sec, new_visit_id)
    assert db.get(Visit, new_visit_id).status == VisitStatus.ONSITE.value


def test_cross_location_emergency_isolation(client):
    c, TestingSessionLocal, session = client
    owner = _ctx(session, "sheru.bohra@lazypay.in")
    blr = session.query(Location).filter(Location.code == "BLR").first()
    mum = session.query(Location).filter(Location.code == "MUM").first()
    start_emergency(session, owner, blr.id, "EMERGENCY")
    mum_event = start_emergency(session, owner, mum.id, "EVACUATION_DRILL")
    r = c.get(f"/api/emergencies/{mum_event['id']}", headers={"X-Dev-User-Email": "security.blr@vms.local"})
    assert r.status_code == 403


def test_bangalore_emergency_e2e(test_db):
    TestingSessionLocal, _, session = test_db
    owner = _ctx(session, "sheru.bohra@lazypay.in")
    sec = _ctx(session, "security.blr@vms.local")
    visits = []
    for i in range(3):
        v, loc = _onsite_visit(session, f"{i:03d}")
        visits.append(v)
    event = start_emergency(session, owner, loc.id, "EMERGENCY")
    assert event["visitor_snapshot_count"] == 3
    entries = list_roll_call(session, owner, event["id"])
    assert len(entries) == 3
    statuses = [RollCallEntryStatus.SAFE.value, RollCallEntryStatus.NOT_LOCATED.value, RollCallEntryStatus.LEFT_PREMISES.value]
    for entry, st in zip(entries, statuses):
        update_roll_call_status(session, owner, event["id"], entry["id"], st)
    detail = get_emergency(session, owner, event["id"])
    assert detail["counts"]["safe"] == 1
    assert detail["counts"]["not_located"] == 1
    assert detail["counts"]["left_premises"] == 1
    from tests.test_phase4 import _create_approved_visit
    from app.application.security_screening_service import screen_visit
    from app.application.security_review_service import resolve_clear
    from app.domain.enums import SecurityClearanceStatus
    blocked_visit, _ = _create_approved_visit(session, "BLR", "e2eblock")
    blocked_id = blocked_visit.id
    db = TestingSessionLocal()
    mark_arrived(db, sec, blocked_id)
    screen_visit(db, blocked_id, trigger="check_in")
    blocked = db.get(Visit, blocked_id)
    if blocked and blocked.security_clearance_status == SecurityClearanceStatus.REVIEW.value:
        resolve_clear(db, sec, blocked_id, comment="clear")
    try:
        with pytest.raises(OperationsError):
            check_in_visit(db, sec, blocked_id)
    finally:
        db.close()
    not_located = [e for e in list_roll_call(session, owner, event["id"]) if e["status"] == RollCallEntryStatus.NOT_LOCATED.value][0]
    update_roll_call_status(session, owner, event["id"], not_located["id"], RollCallEntryStatus.SAFE.value)
    close_emergency(session, owner, event["id"])
    reopen_visit, _ = _create_approved_visit(session, "BLR", "e2eopen")
    reopen_id = reopen_visit.id
    db2 = TestingSessionLocal()
    try:
        mark_arrived(db2, sec, reopen_id)
        screen_visit(db2, reopen_id, trigger="check_in")
        reopen = db2.get(Visit, reopen_id)
        if reopen and reopen.security_clearance_status == SecurityClearanceStatus.REVIEW.value:
            resolve_clear(db2, sec, reopen_id, comment="clear")
        check_in_visit(db2, sec, reopen_id)
    finally:
        db2.close()
    session.expire_all()
    assert session.get(Visit, reopen_id).status == VisitStatus.ONSITE.value


def test_security_cannot_view_mumbai_roll_call(client):
    c, _, session = client
    owner = _ctx(session, "sheru.bohra@lazypay.in")
    mum = session.query(Location).filter(Location.code == "MUM").first()
    event = start_emergency(session, owner, mum.id, "EMERGENCY")
    r = c.get(f"/api/emergencies/{event['id']}/roll-call", headers={"X-Dev-User-Email": "security.blr@vms.local"})
    assert r.status_code == 403
