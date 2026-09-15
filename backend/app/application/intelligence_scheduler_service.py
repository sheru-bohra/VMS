"""Periodic visitor intelligence insight generation."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.application.visitor_intelligence_service import generate_insights_for_locations
from app.domain.models import Location


def run_intelligence_cycle(db: Session) -> int:
    location_ids = [r[0] for r in db.query(Location.id).filter(Location.is_active.is_(True)).all()]
    if not location_ids:
        return 0
    return generate_insights_for_locations(db, location_ids)
