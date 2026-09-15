"""Remove development/demo seed data from the application database."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.application.bootstrap import (
    DEV_LOCATION_B_CODE,
    DEV_LOCATION_CODE,
    DEV_USERS,
    OWNER_EMAIL,
    SITE_ADMIN_EMAIL,
)
from app.application.uat_data_service import cleanup_uat_synthetic_data
from app.domain.models import (
    AccessProfile,
    AccessProvisioningAttempt,
    AdminUser,
    AIInsight,
    AIInteraction,
    AISession,
    BadgePrintJob,
    BadgePrinter,
    EmergencyEvent,
    EmergencyRollCallAction,
    EmergencyRollCallEntry,
    Host,
    HostLocationAssignment,
    Location,
    LocationAccessConfiguration,
    Notification,
    SecurityScreening,
    UserLocationAssignment,
    VendorCompany,
    VendorCompanyLocation,
    VendorVisitorProfile,
    Visit,
    Visitor,
    VisitorAccessCredential,
    VisitorTypeAccessProfile,
    WatchlistEntry,
)
DEMO_USER_EMAILS = frozenset(
    email for email, _, _, _ in DEV_USERS
) | {
    SITE_ADMIN_EMAIL,
    "headadmin@vms.local",
    "security.blr@vms.local",
    "security.mum@vms.local",
    "siteadmin.blr@vms.local",
    "siteadmin.mum@vms.local",
}

DEV_LOCATION_CODES = frozenset({DEV_LOCATION_CODE, DEV_LOCATION_B_CODE})
LEGACY_DUPLICATE_LOCATION_CODES = frozenset({"PUNE"})


def _delete_visits_for_locations(db: Session, location_ids: List[int]) -> int:
    if not location_ids:
        return 0
    visits = (
        db.query(Visit)
        .filter(
            (Visit.location_id.in_(location_ids))
            | (Visit.arrival_location_id.in_(location_ids))
            | (Visit.check_in_location_id.in_(location_ids))
        )
        .all()
    )
    count = len(visits)
    for visit in visits:
        db.delete(visit)
    return count


def _delete_visits_for_hosts(db: Session, host_ids: List[int]) -> int:
    if not host_ids:
        return 0
    visits = db.query(Visit).filter(Visit.host_id.in_(host_ids)).all()
    count = len(visits)
    for visit in visits:
        db.delete(visit)
    return count


def _delete_location_dependencies(db: Session, location_id: int) -> None:
    cred_ids = [
        row.id
        for row in db.query(VisitorAccessCredential.id).filter(
            VisitorAccessCredential.location_id == location_id
        )
    ]
    if cred_ids:
        db.query(AccessProvisioningAttempt).filter(
            AccessProvisioningAttempt.access_credential_id.in_(cred_ids)
        ).delete(synchronize_session=False)
        db.query(VisitorAccessCredential).filter(
            VisitorAccessCredential.id.in_(cred_ids)
        ).delete(synchronize_session=False)

    db.query(BadgePrintJob).filter(BadgePrintJob.location_id == location_id).delete(
        synchronize_session=False
    )
    db.query(BadgePrinter).filter(BadgePrinter.location_id == location_id).delete(
        synchronize_session=False
    )

    event_ids = [
        row.id for row in db.query(EmergencyEvent.id).filter(EmergencyEvent.location_id == location_id)
    ]
    if event_ids:
        entry_ids = [
            row.id
            for row in db.query(EmergencyRollCallEntry.id).filter(
                EmergencyRollCallEntry.emergency_event_id.in_(event_ids)
            )
        ]
        if entry_ids:
            db.query(EmergencyRollCallAction).filter(
                EmergencyRollCallAction.roll_call_entry_id.in_(entry_ids)
            ).delete(synchronize_session=False)
        db.query(EmergencyRollCallEntry).filter(
            EmergencyRollCallEntry.emergency_event_id.in_(event_ids)
        ).delete(synchronize_session=False)
        db.query(EmergencyEvent).filter(EmergencyEvent.id.in_(event_ids)).delete(
            synchronize_session=False
        )

    db.query(AIInsight).filter(AIInsight.location_id == location_id).delete(synchronize_session=False)
    db.query(WatchlistEntry).filter(WatchlistEntry.location_id == location_id).delete(
        synchronize_session=False
    )
    db.query(Notification).filter(Notification.location_id == location_id).delete(
        synchronize_session=False
    )
    db.query(SecurityScreening).filter(SecurityScreening.location_id == location_id).delete(
        synchronize_session=False
    )
    db.query(VisitorTypeAccessProfile).filter(
        VisitorTypeAccessProfile.location_id == location_id
    ).delete(synchronize_session=False)
    db.query(AccessProfile).filter(AccessProfile.location_id == location_id).delete(
        synchronize_session=False
    )
    db.query(LocationAccessConfiguration).filter(
        LocationAccessConfiguration.location_id == location_id
    ).delete(synchronize_session=False)
    db.query(VendorCompanyLocation).filter(VendorCompanyLocation.location_id == location_id).delete(
        synchronize_session=False
    )
    db.query(UserLocationAssignment).filter(UserLocationAssignment.location_id == location_id).delete(
        synchronize_session=False
    )
    db.query(HostLocationAssignment).filter(HostLocationAssignment.location_id == location_id).delete(
        synchronize_session=False
    )


def _delete_orphan_visitors(db: Session) -> int:
    visitor_ids_with_visits = {row[0] for row in db.query(Visit.visitor_id).distinct()}
    orphans = db.query(Visitor).filter(~Visitor.id.in_(visitor_ids_with_visits)).all()
    count = len(orphans)
    for visitor in orphans:
        db.query(VendorVisitorProfile).filter(VendorVisitorProfile.visitor_id == visitor.id).delete(
            synchronize_session=False
        )
        db.delete(visitor)
    return count


def purge_development_seed_data(db: Session) -> Dict[str, Any]:
    """Idempotently remove demo users, dev locations, dev hosts, and related operational data."""
    summary: Dict[str, Any] = {
        "demo_users_removed": 0,
        "dev_hosts_removed": 0,
        "dev_locations_removed": 0,
        "visits_removed": 0,
        "orphan_visitors_removed": 0,
        "uat_visitors_removed": 0,
        "vendor_companies_removed": 0,
        "ai_interactions_removed": 0,
        "ai_sessions_removed": 0,
        "ai_insights_removed": 0,
        "watchlist_removed": 0,
    }

    uat_result = cleanup_uat_synthetic_data(db)
    summary["uat_visitors_removed"] = uat_result.get("visitors_removed", 0)

    demo_users = (
        db.query(AdminUser)
        .filter(AdminUser.email.in_(DEMO_USER_EMAILS))
        .filter(AdminUser.is_owner.is_(False))
        .all()
    )
    for user in demo_users:
        db.query(UserLocationAssignment).filter(
            UserLocationAssignment.admin_user_id == user.id
        ).delete(synchronize_session=False)
        db.query(AISession).filter(AISession.user_id == user.id).delete(synchronize_session=False)
        db.query(AIInteraction).filter(AIInteraction.user_id == user.id).delete(synchronize_session=False)
        db.delete(user)
        summary["demo_users_removed"] += 1

    dev_hosts = db.query(Host).filter(Host.is_development_seed.is_(True)).all()
    dev_host_ids = [host.id for host in dev_hosts]
    summary["visits_removed"] += _delete_visits_for_hosts(db, dev_host_ids)
    for host in dev_hosts:
        db.query(HostLocationAssignment).filter(HostLocationAssignment.host_id == host.id).delete(
            synchronize_session=False
        )
        db.delete(host)
        summary["dev_hosts_removed"] += 1

    dev_locations = (
        db.query(Location)
        .filter(
            (Location.is_development_seed.is_(True))
            | (Location.code.in_(DEV_LOCATION_CODES))
            | (Location.code.in_(LEGACY_DUPLICATE_LOCATION_CODES))
        )
        .all()
    )
    dev_location_ids = [loc.id for loc in dev_locations]
    summary["visits_removed"] += _delete_visits_for_locations(db, dev_location_ids)
    for loc in dev_locations:
        _delete_location_dependencies(db, loc.id)
        db.delete(loc)
        summary["dev_locations_removed"] += 1

    summary["orphan_visitors_removed"] = _delete_orphan_visitors(db)

    demo_vendors = (
        db.query(VendorCompany)
        .filter(
            VendorCompany.name.ilike("UAT-%")
            | VendorCompany.name.ilike("%demo%")
            | VendorCompany.name.ilike("%sample%")
        )
        .all()
    )
    for company in demo_vendors:
        db.query(VendorCompanyLocation).filter(
            VendorCompanyLocation.vendor_company_id == company.id
        ).delete(synchronize_session=False)
        db.query(VendorVisitorProfile).filter(
            VendorVisitorProfile.vendor_company_id == company.id
        ).delete(synchronize_session=False)
        db.delete(company)
        summary["vendor_companies_removed"] += 1

    summary["ai_interactions_removed"] = db.query(AIInteraction).delete(synchronize_session=False)
    summary["ai_sessions_removed"] = db.query(AISession).delete(synchronize_session=False)
    summary["ai_insights_removed"] = db.query(AIInsight).delete(synchronize_session=False)
    summary["watchlist_removed"] = db.query(WatchlistEntry).delete(synchronize_session=False)

    owner = db.query(AdminUser).filter(AdminUser.email.ilike(OWNER_EMAIL)).first()
    if owner:
        owner.is_active = True
        owner.is_owner = True

    db.flush()
    return summary
