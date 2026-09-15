import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.application.approval_service import approve_visit, reject_visit
from app.application.auth_service import build_auth_context
from app.application.bootstrap import bootstrap_development_data, DEV_LOCATION_CODE, SITE_ADMIN_EMAIL
from app.domain.enums import ApprovalDecision, RejectionReason, VisitStatus
from app.domain.models import AdminUser, Location, Visit, VisitApproval
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


def _create_pending_visit(session, suffix="1"):
    from app.domain.models import Visitor, VisitorType, Host, HostLocationAssignment

    loc = session.query(Location).filter(Location.code == DEV_LOCATION_CODE).first()
    vt = session.query(VisitorType).filter(VisitorType.code == "BUSINESS").first()
    host = session.query(Host).filter(Host.is_development_seed.is_(True)).first()
    visitor = Visitor(
        full_name=f"Pending Visitor {suffix}",
        email=f"pending{suffix}@test.com",
        phone=f"+91999{suffix}00000",
        company="Test Co",
        visitor_type_id=vt.id,
    )
    session.add(visitor)
    session.flush()
    visit = Visit(
        visitor_id=visitor.id,
        location_id=loc.id,
        status=VisitStatus.PENDING_APPROVAL.value,
        registration_reference=f"VMS-TEST-{suffix}",
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


def _owner_ctx(session):
    owner = session.query(AdminUser).filter(AdminUser.email == "sheru.bohra@lazypay.in").first()
    return build_auth_context(owner)


def _site_admin_ctx(session):
    admin = session.query(AdminUser).filter(AdminUser.email == SITE_ADMIN_EMAIL).first()
    return build_auth_context(admin)


def test_pending_visit_can_be_approved(test_db):
    TestingSessionLocal, _, bootstrap_session = test_db
    visit = _create_pending_visit(bootstrap_session, "approve")
    ctx = _owner_ctx(bootstrap_session)
    db = TestingSessionLocal()
    result = approve_visit(db, ctx, visit.id, comment="Welcome")
    assert result["status"] == VisitStatus.APPROVED.value
    approval = bootstrap_session.query(VisitApproval).filter(VisitApproval.visit_id == visit.id).first()
    assert approval is not None
    assert approval.decision == ApprovalDecision.APPROVED.value
    db.close()


def test_pending_visit_can_be_rejected(test_db):
    TestingSessionLocal, _, bootstrap_session = test_db
    visit = _create_pending_visit(bootstrap_session, "reject")
    ctx = _owner_ctx(bootstrap_session)
    db = TestingSessionLocal()
    result = reject_visit(
        db, ctx, visit.id,
        reason_code=RejectionReason.HOST_UNAVAILABLE.value,
        comment=None,
    )
    assert result["status"] == VisitStatus.REJECTED.value
    approval = bootstrap_session.query(VisitApproval).filter(VisitApproval.visit_id == visit.id).first()
    assert approval.reason_code == RejectionReason.HOST_UNAVAILABLE.value
    db.close()


def test_approved_visit_idempotent_no_duplicate_history(test_db):
    TestingSessionLocal, _, bootstrap_session = test_db
    visit = _create_pending_visit(bootstrap_session, "reapprove")
    ctx = _owner_ctx(bootstrap_session)
    db = TestingSessionLocal()
    approve_visit(db, ctx, visit.id)
    approve_visit(db, ctx, visit.id)
    count = bootstrap_session.query(VisitApproval).filter(VisitApproval.visit_id == visit.id).count()
    assert count == 1
    db.close()


def test_rejected_visit_cannot_be_approved(test_db):
    TestingSessionLocal, _, bootstrap_session = test_db
    visit = _create_pending_visit(bootstrap_session, "rejtoapp")
    ctx = _owner_ctx(bootstrap_session)
    db = TestingSessionLocal()
    reject_visit(db, ctx, visit.id, reason_code=RejectionReason.DUPLICATE_REQUEST.value)
    from app.application.approval_service import ApprovalConflictError
    with pytest.raises(ApprovalConflictError):
        approve_visit(db, ctx, visit.id)
    db.close()


def test_rejection_requires_reason(test_db):
    TestingSessionLocal, _, bootstrap_session = test_db
    visit = _create_pending_visit(bootstrap_session, "noreason")
    ctx = _owner_ctx(bootstrap_session)
    db = TestingSessionLocal()
    from app.application.approval_service import ApprovalError
    with pytest.raises(ApprovalError):
        reject_visit(db, ctx, visit.id, reason_code="INVALID", comment=None)
    db.close()


def test_other_rejection_requires_comment(test_db):
    TestingSessionLocal, _, bootstrap_session = test_db
    visit = _create_pending_visit(bootstrap_session, "other")
    ctx = _owner_ctx(bootstrap_session)
    db = TestingSessionLocal()
    from app.application.approval_service import ApprovalError
    with pytest.raises(ApprovalError):
        reject_visit(db, ctx, visit.id, reason_code=RejectionReason.OTHER.value, comment=None)
    db.close()


def test_site_admin_service_can_approve_assigned_site(test_db):
    TestingSessionLocal, _, bootstrap_session = test_db
    visit = _create_pending_visit(bootstrap_session, "siteadmin")
    ctx = _site_admin_ctx(bootstrap_session)
    db = TestingSessionLocal()
    result = approve_visit(db, ctx, visit.id)
    assert result["status"] == VisitStatus.APPROVED.value
    db.close()


def test_site_admin_api_approve_own_site(client, test_db):
    c, session_factory, bootstrap_session = client
    visit = _create_pending_visit(bootstrap_session, "sitea")
    r = c.post(f"/api/approvals/{visit.id}/approve", json={"comment": "ok"})
    assert r.status_code == 200
    assert r.json()["status"] == VisitStatus.APPROVED.value


def test_site_admin_cannot_approve_other_site(client, test_db):
    c, session_factory, bootstrap_session = client
    from app.domain.models import Host, HostLocationAssignment
    loc_b = bootstrap_session.query(Location).filter(Location.code == "DEV-SITE-B").first()
    visit = _create_pending_visit(bootstrap_session, "cross")
    visit.location_id = loc_b.id
    bootstrap_session.commit()

    # Simulate site admin via direct service call
    ctx = _site_admin_ctx(bootstrap_session)
    db = session_factory()
    from app.application.approval_service import ApprovalError
    with pytest.raises(ApprovalError) as exc:
        approve_visit(db, ctx, visit.id)
    assert exc.value.status_code == 403
    db.close()


def test_concurrent_decision_conflict(test_db):
    TestingSessionLocal, _, bootstrap_session = test_db
    visit = _create_pending_visit(bootstrap_session, "concurrent")
    ctx = _owner_ctx(bootstrap_session)
    db1 = TestingSessionLocal()
    db2 = TestingSessionLocal()
    approve_visit(db1, ctx, visit.id)
    from app.application.approval_service import ApprovalConflictError
    with pytest.raises(ApprovalConflictError):
        reject_visit(
            db2, ctx, visit.id,
            reason_code=RejectionReason.DUPLICATE_REQUEST.value,
        )
    count = bootstrap_session.query(VisitApproval).filter(VisitApproval.visit_id == visit.id).count()
    assert count == 1
    db1.close()
    db2.close()


def test_double_approve_idempotent(test_db):
    TestingSessionLocal, _, bootstrap_session = test_db
    visit = _create_pending_visit(bootstrap_session, "idempotent")
    ctx = _owner_ctx(bootstrap_session)
    db = TestingSessionLocal()
    approve_visit(db, ctx, visit.id)
    approve_visit(db, ctx, visit.id)
    count = bootstrap_session.query(VisitApproval).filter(VisitApproval.visit_id == visit.id).count()
    assert count == 1
    db.close()


def test_approval_api_list(client, test_db):
    c, _, bootstrap_session = client
    _create_pending_visit(bootstrap_session, "api")
    r = c.get("/api/approvals?status=PENDING_APPROVAL")
    assert r.status_code == 200
    data = r.json()
    assert data["pending_count"] >= 1
    assert data["total"] >= 1


def test_audit_on_approve(test_db):
    TestingSessionLocal, _, bootstrap_session = test_db
    from app.domain.models import AuditEvent
    visit = _create_pending_visit(bootstrap_session, "audit")
    ctx = _owner_ctx(bootstrap_session)
    db = TestingSessionLocal()
    approve_visit(db, ctx, visit.id)
    event = bootstrap_session.query(AuditEvent).filter(
        AuditEvent.action == "VISITOR_APPROVED",
        AuditEvent.entity_id == str(visit.id),
    ).first()
    assert event is not None
    db.close()
