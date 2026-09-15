"""Optional live PostgreSQL integration tests — destructive; gated."""

import os

import pytest

from tests.integration.live.conftest import validate_postgres_test_url

if not os.environ.get("TEST_POSTGRES_URL"):
    pytest.skip("TEST_POSTGRES_URL not configured", allow_module_level=True)

if os.environ.get("ALLOW_POSTGRES_TEST_DATABASE") != "true":
    pytest.skip("ALLOW_POSTGRES_TEST_DATABASE=true required", allow_module_level=True)

if os.environ.get("ENABLE_LIVE_INTEGRATION_TESTS") != "true":
    pytest.skip("ENABLE_LIVE_INTEGRATION_TESTS=true required", allow_module_level=True)

validate_postgres_test_url(os.environ["TEST_POSTGRES_URL"])

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.application.bootstrap import bootstrap_development_data
from app.domain.models import Base


@pytest.fixture(scope="module")
def postgres_engine():
    from tests.integration.live.conftest import require_live_integration_enabled

    require_live_integration_enabled()
    url = os.environ["TEST_POSTGRES_URL"]
    engine = create_engine(url, pool_pre_ping=True)
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    bootstrap_development_data(db)
    db.close()
    yield engine
    engine.dispose()
