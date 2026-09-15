"""Synthetic UAT fixture seeding (optional, development/UAT only)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.domain.models import Visitor, VisitorType


UAT_EMAIL_DOMAIN = "example.invalid"
UAT_NAME_PREFIX = "UAT-"


def seed_uat_synthetic_visitors(db: Session) -> int:
    """Create identifiable synthetic visitors for manual UAT. Skips if already present."""
    created = 0
    visitor_types = db.query(VisitorType).filter(VisitorType.is_active.is_(True)).limit(6).all()
    if not visitor_types:
        return 0
    for idx, vtype in enumerate(visitor_types, start=1):
        email = f"uat-visitor-{idx:03d}@{UAT_EMAIL_DOMAIN}"
        existing = db.query(Visitor).filter(Visitor.email == email).first()
        if existing:
            continue
        db.add(
            Visitor(
                full_name=f"{UAT_NAME_PREFIX}Visitor {idx:03d}",
                email=email,
                phone=f"+9100000{idx:04d}",
                company=f"{UAT_NAME_PREFIX}Company",
                visitor_type_id=vtype.id,
            )
        )
        created += 1
    if created:
        db.commit()
    return created


def cleanup_uat_synthetic_data(db: Session) -> dict:
    """Remove synthetic UAT visitors (UAT- prefix / example.invalid). Does not touch audit events."""
    visitors = (
        db.query(Visitor)
        .filter(
            (Visitor.full_name.startswith(UAT_NAME_PREFIX))
            | (Visitor.email.endswith(f"@{UAT_EMAIL_DOMAIN}"))
        )
        .all()
    )
    count = len(visitors)
    for visitor in visitors:
        db.delete(visitor)
    if count:
        db.commit()
    return {"visitors_removed": count}
