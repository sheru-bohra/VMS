"""Live PostgreSQL migration smoke test when TEST_POSTGRES_URL is configured."""

import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

TEST_URL = os.environ.get("TEST_POSTGRES_URL")


@pytest.mark.skipif(not TEST_URL, reason="TEST_POSTGRES_URL not set")
def test_postgres_migrations_to_head():
    if os.environ.get("ALLOW_POSTGRES_TEST_DATABASE") != "true":
        pytest.skip("ALLOW_POSTGRES_TEST_DATABASE=true required")

    engine = create_engine(TEST_URL, pool_pre_ping=True)
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", TEST_URL)
    command.upgrade(cfg, "head")
    command.upgrade(cfg, "head")
    with engine.connect() as conn:
        row = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    script_cfg = Config("alembic.ini")
    from alembic.script import ScriptDirectory

    head = ScriptDirectory.from_config(script_cfg).get_current_head()
    assert row == head
    engine.dispose()
    from app.application.release_evidence import record_live_result
    from app.domain.release_status import IntegrationReleaseStatus

    record_live_result("postgresql", IntegrationReleaseStatus.LIVE_VALIDATED, "migrations=head")
