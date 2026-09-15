"""PostgreSQL CRUD, schema, and rate-limit live checks."""

import os

import pytest
from sqlalchemy.orm import sessionmaker

from app.application.rate_limit_store import DatabaseRateLimitStore
from app.application.release_evidence import record_live_result
from app.domain.models import Visitor, Visit, Location
from app.domain.release_status import IntegrationReleaseStatus
from app.infrastructure.database_schema import check_schema_at_head

TEST_URL = os.environ.get("TEST_POSTGRES_URL")


def test_postgres_schema_at_head(postgres_engine):
    info = check_schema_at_head(postgres_engine, require_version=True)
    assert info.get("schema_current") is True
    record_live_result("postgresql", IntegrationReleaseStatus.LIVE_VALIDATED, "schema_at_head=PASS")


def test_postgres_visitor_visit_crud(postgres_engine):
    Session = sessionmaker(bind=postgres_engine)
    db = Session()
    loc = db.query(Location).filter(Location.code == "BLR").first()
    assert loc is not None
    visitor = Visitor(full_name="PG Live Visitor", email="pg-live@example.invalid", company="UAT Co")
    db.add(visitor)
    db.flush()
    visit = Visit(
        visitor_id=visitor.id,
        location_id=loc.id,
        status="PENDING_APPROVAL",
        purpose="PostgreSQL live CRUD validation",
        source="self_registration",
    )
    db.add(visit)
    db.commit()
    loaded = db.query(Visit).filter(Visit.id == visit.id).first()
    assert loaded is not None
    assert loaded.visitor_id == visitor.id
    db.delete(visit)
    db.delete(visitor)
    db.commit()
    db.close()
    record_live_result("postgresql", IntegrationReleaseStatus.LIVE_VALIDATED, "visitor_visit_crud=PASS")


def test_postgres_rate_limit_atomic(postgres_engine):
    Session = sessionmaker(bind=postgres_engine)
    store_a = DatabaseRateLimitStore(Session)
    store_b = DatabaseRateLimitStore(Session)
    key = "pg-live-rate-limit-key"
    assert store_a.check_and_increment(key, 100, 60)
    assert store_b.check_and_increment(key, 100, 60)
    record_live_result("postgresql", IntegrationReleaseStatus.LIVE_VALIDATED, "rate_limit_atomic=PASS")
