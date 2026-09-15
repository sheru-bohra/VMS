import os

import pytest

os.environ.setdefault("BACKGROUND_SCHEDULER_ENABLED", "false")
os.environ.setdefault(
    "AUDIT_INTEGRITY_KEY",
    "phase13-audit-integrity-key-for-local-vms-session-only-32c",
)
os.environ.setdefault(
    "DOCUMENT_ENCRYPTION_KEY",
    "phase13-document-encryption-key-for-local-vms-only-32chars",
)

from app.application.bootstrap import OWNER_EMAIL
from app.core.config import settings


def pytest_configure(config):
    config.addinivalue_line("markers", "release: Release candidate regression tests")


@pytest.fixture(autouse=True)
def isolate_test_runtime(monkeypatch):
    """Keep tests isolated from local .env auth mode and lifespan DB bootstrap."""
    monkeypatch.setattr("app.main.purge_development_seed_data", lambda db: {})
    monkeypatch.setattr("app.main.bootstrap_application_data", lambda db: None)
    monkeypatch.setattr(settings, "auth_mode", "dev")
    monkeypatch.setattr(settings, "dev_auth_enabled", True)
    monkeypatch.setattr(settings, "dev_auth_email", OWNER_EMAIL)
