"""Phase 16.1 automated closure regressions (no live external integrations)."""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from app.application.audit_integrity_service import verify_chain
from app.application.audit_service import AuditService
from app.application.bootstrap import bootstrap_development_data
from app.application.document_encryption import DocumentEncryptionError, decrypt_bytes, encrypt_bytes
from cryptography.exceptions import InvalidTag
from app.application.release_evidence import load_evidence
from app.application.release_readiness_service import build_release_matrix
from app.core.config import settings
from app.domain.models import Base
from app.infrastructure.database import get_db
from app.main import create_app, _stop_scheduler

pytestmark = pytest.mark.release


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
    _stop_scheduler()


def test_db_outage_safe_responses(client):
    c, _, _ = client

    class FailingSession:
        def execute(self, *args, **kwargs):
            raise OperationalError("SELECT 1", {}, Exception("connection refused"))

        def get_bind(self):
            raise OperationalError("bind", {}, Exception("connection refused"))

    def failing_db():
        yield FailingSession()

    c.app.dependency_overrides[get_db] = failing_db
    live = c.get("/api/health/live")
    assert live.status_code == 200
    ready = c.get("/api/health/ready")
    assert ready.status_code == 503
    body = ready.json()
    assert body.get("error", {}).get("code") == "DATABASE_UNAVAILABLE"
    assert "password" not in ready.text.lower()
    assert "secret" not in ready.text.lower()


def test_audit_key_wrong_key_fails_verification(test_db, monkeypatch):
    _, _, session = test_db
    AuditService(session).record(action="KEY_TEST", entity_type="TEST", entity_id="1")
    session.commit()
    assert verify_chain(session).get("status") == "VALID"
    monkeypatch.setattr(settings, "audit_integrity_key", "wrong-audit-integrity-key-for-test-only-32c")
    result = verify_chain(session)
    assert result.get("status") != "VALID"


def test_encryption_key_recovery_roundtrip(monkeypatch):
    key = "abcdefghijklmnopabcdefghijklmnop1234"
    monkeypatch.setattr(settings, "document_encryption_key", key)
    blob, ver = encrypt_bytes(b"closure-phase-data")
    assert decrypt_bytes(blob, ver) == b"closure-phase-data"


def test_encryption_wrong_key_fails_safely(monkeypatch):
    key = "abcdefghijklmnopabcdefghijklmnop1234"
    monkeypatch.setattr(settings, "document_encryption_key", key)
    blob, ver = encrypt_bytes(b"closure-phase-data")
    monkeypatch.setattr(settings, "document_encryption_key", "wrongkeywrongkeywrongkeywrongkey12")
    with pytest.raises((DocumentEncryptionError, InvalidTag)):
        decrypt_bytes(blob, ver)


def test_evidence_matrix_requires_live_record_for_postgresql():
    evidence = load_evidence()
    matrix = build_release_matrix(True)
    if matrix.get("postgresql") == "LIVE_VALIDATED":
        assert evidence.get("postgresql", {}).get("status") == "LIVE_VALIDATED"
