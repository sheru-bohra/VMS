import os
import tempfile
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.application.approval_service import approve_visit
from app.application.auth_service import build_auth_context
from app.application.bootstrap import bootstrap_development_data
from app.application.host_approval_service import (
    create_host_approval_request,
    get_public_host_approval_summary,
    host_approve,
    host_reject,
)
from app.application.invitation_service import create_advance_visit
from app.application.operations_service import check_in_visit, mark_arrived
from app.application.registration_service import create_self_registration
from app.application.token_service import hash_host_approval_token
from app.core.config import settings
from app.domain.enums import (
    ApprovalActorType,
    HostApprovalRequestStatus,
    NotificationType,
    VisitSource,
    VisitStatus,
)
from app.domain.models import (
    AdminUser,
    Host,
    HostApprovalRequest,
    HostLocationAssignment,
    Location,
    Notification,
    Visit,
    VisitApproval,
    Visitor,
    VisitorType,
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


def _owner_ctx(session):
    owner = session.query(AdminUser).filter(AdminUser.email == "sheru.bohra@lazypay.in").first()
    return build_auth_context(owner)


def _blr_host(session):
    loc = session.query(Location).filter(Location.code == "BLR").first()
    ha = session.query(HostLocationAssignment).filter(HostLocationAssignment.location_id == loc.id).first()
    host = session.query(Host).filter(Host.id == ha.host_id).first()
    return host, loc


def _visit_by_email(session, email: str) -> Visit:
    return session.query(Visit).join(Visitor).filter(Visitor.email == email).first()


def test_self_registration_creates_host_approval_request(test_db):
    TestingSessionLocal, _, session = test_db
    host, loc = _blr_host(session)
    db = TestingSessionLocal()
    result = create_self_registration(
        db,
        site_token=loc.public_registration_token,
        visitor_type_code="BUSINESS",
        full_name="Walk Host Test",
        mobile="+91988111222",
        email="walkhost@test.com",
        company="Walk Co",
        host_id=host.id,
        purpose="Meeting",
        expected_duration_minutes=60,
        policy_accepted=True,
    )
    visit = session.query(Visit).filter(Visit.registration_reference == result["registration_reference"]).first()
    req = session.query(HostApprovalRequest).filter(HostApprovalRequest.visit_id == visit.id).first()
    assert req is not None
    assert req.status == HostApprovalRequestStatus.PENDING.value
    assert req.token_hash != ""
    assert len(req.token_hash) == 64
    notif = session.query(Notification).filter(
        Notification.visit_id == visit.id,
        Notification.notification_type == NotificationType.HOST_APPROVAL_REQUEST.value,
    ).first()
    assert notif is not None


def test_token_hashed_not_stored_raw(test_db):
    _, _, session = test_db
    host, loc = _blr_host(session)
    visit = Visit(
        visitor_id=session.query(Visit).first().visitor_id if session.query(Visit).first() else 1,
        location_id=loc.id,
        status=VisitStatus.PENDING_APPROVAL.value,
        host_id=host.id,
        host_name=host.name,
        source=VisitSource.SELF_REGISTRATION.value,
        policy_accepted=True,
    )
    # use existing visitor from bootstrap
    vt = session.query(VisitorType).filter(VisitorType.code == "BUSINESS").first()
    visitor = Visitor(full_name="Token Test", email="tok@test.com", phone="+91999000001", company="Co", visitor_type_id=vt.id)
    session.add(visitor)
    session.flush()
    visit.visitor_id = visitor.id
    session.add(visit)
    session.flush()
    req = create_host_approval_request(session, visit.id)
    session.commit()
    assert req is not None
    stored = session.query(HostApprovalRequest).filter(HostApprovalRequest.id == req.id).first()
    assert stored.token_hash is not None
    assert len(stored.token_hash) == 64


def test_host_approve_via_token(test_db):
    TestingSessionLocal, _, session = test_db
    host, loc = _blr_host(session)
    db = TestingSessionLocal()
    create_self_registration(
        db,
        site_token=loc.public_registration_token,
        visitor_type_code="BUSINESS",
        full_name="Host Approve Test",
        mobile="+91988111333",
        email="hostappr@test.com",
        company="Co",
        host_id=host.id,
        purpose="Meeting",
        expected_duration_minutes=60,
        policy_accepted=True,
    )
    visit = (
        session.query(Visit)
        .join(Visitor)
        .filter(Visitor.email == "hostappr@test.com")
        .first()
    )
    notif = session.query(Notification).filter(Notification.visit_id == visit.id).first()
    assert notif and notif.dev_action_url
    token = notif.dev_action_url.rsplit("/", 1)[-1]
    result = host_approve(db, token)
    assert result["state"] == "APPROVED"
    session.refresh(visit)
    assert visit.status == VisitStatus.APPROVED.value
    approval = session.query(VisitApproval).filter(VisitApproval.visit_id == visit.id).first()
    assert approval.actor_type == ApprovalActorType.HOST_LINK.value
    assert approval.actor_host_id == host.id


def test_host_reject_via_token(test_db):
    TestingSessionLocal, _, session = test_db
    host, loc = _blr_host(session)
    db = TestingSessionLocal()
    create_self_registration(
        db,
        site_token=loc.public_registration_token,
        visitor_type_code="BUSINESS",
        full_name="Host Reject Test",
        mobile="+91988111444",
        email="hostrej@test.com",
        company="Co",
        host_id=host.id,
        purpose="Meeting",
        expected_duration_minutes=60,
        policy_accepted=True,
    )
    visit = _visit_by_email(session, "hostrej@test.com")
    notif = session.query(Notification).filter(Notification.visit_id == visit.id).first()
    token = notif.dev_action_url.rsplit("/", 1)[-1]
    result = host_reject(db, token, "HOST_UNAVAILABLE", None)
    assert result["state"] == "REJECTED"
    session.refresh(visit)
    assert visit.status == VisitStatus.REJECTED.value


def test_admin_first_invalidates_host_link(test_db):
    TestingSessionLocal, _, session = test_db
    host, loc = _blr_host(session)
    db = TestingSessionLocal()
    create_self_registration(
        db,
        site_token=loc.public_registration_token,
        visitor_type_code="BUSINESS",
        full_name="Admin First",
        mobile="+91988111555",
        email="adminfirst@test.com",
        company="Co",
        host_id=host.id,
        purpose="Meeting",
        expected_duration_minutes=60,
        policy_accepted=True,
    )
    visit = _visit_by_email(session, "adminfirst@test.com")
    notif = session.query(Notification).filter(Notification.visit_id == visit.id).first()
    token = notif.dev_action_url.rsplit("/", 1)[-1]
    owner = _owner_ctx(session)
    approve_visit(db, owner, visit.id)
    summary = get_public_host_approval_summary(db, token)
    assert summary["state"] in ("ALREADY_PROCESSED", "REVOKED")
    count = session.query(VisitApproval).filter(VisitApproval.visit_id == visit.id).count()
    assert count == 1


def test_host_first_blocks_admin_reject(test_db):
    TestingSessionLocal, _, session = test_db
    host, loc = _blr_host(session)
    db = TestingSessionLocal()
    create_self_registration(
        db,
        site_token=loc.public_registration_token,
        visitor_type_code="BUSINESS",
        full_name="Host First",
        mobile="+91988111666",
        email="hostfirst@test.com",
        company="Co",
        host_id=host.id,
        purpose="Meeting",
        expected_duration_minutes=60,
        policy_accepted=True,
    )
    visit = _visit_by_email(session, "hostfirst@test.com")
    notif = session.query(Notification).filter(Notification.visit_id == visit.id).first()
    token = notif.dev_action_url.rsplit("/", 1)[-1]
    host_approve(db, token)
    owner = _owner_ctx(session)
    from app.application.approval_service import ApprovalConflictError, reject_visit
    with pytest.raises(ApprovalConflictError):
        reject_visit(db, owner, visit.id, "HOST_UNAVAILABLE")


def test_check_in_queues_arrival_notification_once(test_db):
    TestingSessionLocal, _, session = test_db
    host, loc = _blr_host(session)
    db = TestingSessionLocal()
    owner = _owner_ctx(session)
    create_self_registration(
        db,
        site_token=loc.public_registration_token,
        visitor_type_code="BUSINESS",
        full_name="Arrival Notify",
        mobile="+91988111777",
        email="arrival@test.com",
        company="Co",
        host_id=host.id,
        purpose="Meeting",
        expected_duration_minutes=60,
        policy_accepted=True,
    )
    visit = _visit_by_email(session, "arrival@test.com")
    approve_visit(db, owner, visit.id)
    from app.application.auth_service import build_auth_context
    sec = session.query(AdminUser).filter(AdminUser.email == "security.blr@vms.local").first()
    sec_ctx = build_auth_context(sec)
    mark_arrived(db, sec_ctx, visit.id)
    check_in_visit(db, sec_ctx, visit.id)
    check_in_visit(db, sec_ctx, visit.id)
    count = session.query(Notification).filter(
        Notification.visit_id == visit.id,
        Notification.notification_type == NotificationType.VISITOR_ARRIVED.value,
    ).count()
    assert count == 1


def test_registration_notification_dedupe(test_db):
    TestingSessionLocal, _, session = test_db
    host, loc = _blr_host(session)
    db = TestingSessionLocal()
    create_self_registration(
        db,
        site_token=loc.public_registration_token,
        visitor_type_code="BUSINESS",
        full_name="Dedupe Test",
        mobile="+91988111888",
        email="dedupe@test.com",
        company="Co",
        host_id=host.id,
        purpose="Meeting",
        expected_duration_minutes=60,
        policy_accepted=True,
    )
    visit = _visit_by_email(session, "dedupe@test.com")
    create_host_approval_request(db, visit.id)
    db.commit()
    count = session.query(Notification).filter(
        Notification.visit_id == visit.id,
        Notification.notification_type == NotificationType.HOST_APPROVAL_REQUEST.value,
    ).count()
    assert count == 1


def test_dev_outbox_requires_global_admin(client):
    c, _, _ = client
    r = c.get("/api/dev/notifications", headers={"X-Dev-User-Email": "security.blr@vms.local"})
    assert r.status_code == 403


def test_dev_outbox_global_admin(client):
    c, _, session = client
    host, loc = _blr_host(session)
    c.post(
        "/api/public/registrations",
        json={
            "site_token": loc.public_registration_token,
            "visitor_type": "BUSINESS",
            "full_name": "Outbox Test",
            "mobile": "+91988111999",
            "email": "outbox@test.com",
            "company": "Co",
            "host_id": host.id,
            "purpose": "Meeting",
            "expected_duration_minutes": 60,
            "policy_accepted": True,
        },
    )
    r = c.get("/api/dev/notifications", headers={"X-Dev-User-Email": "sheru.bohra@lazypay.in"})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 1
    approval_items = [i for i in data["items"] if i["notification_type"] == "HOST_APPROVAL_REQUEST"]
    assert approval_items
    assert approval_items[0]["dev_action_url"]


def test_invalid_host_token_rejected(test_db):
    TestingSessionLocal, _, session = test_db
    db = TestingSessionLocal()
    from app.application.host_approval_service import HostApprovalError
    with pytest.raises(HostApprovalError):
        get_public_host_approval_summary(db, "totally-invalid-token-value")
