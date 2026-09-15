from sqlalchemy.orm import Session

from typing import Optional

from app.application.audit_service import AuditService
from app.application.token_service import generate_public_token
from app.domain.enums import AdminRole
from app.domain.models import (
    AdminUser,
    ComplianceRequirement,
    Host,
    HostLocationAssignment,
    Location,
    LocationAccessConfiguration,
    UserLocationAssignment,
    VisitorType,
)

OWNER_EMAIL = "sheru.bohra@lazypay.in"
LEGACY_OWNER_EMAIL = "sheru.bohra@payu.in"
DEV_LOCATION_CODE = "DEV-MAIN"
DEV_LOCATION_B_CODE = "DEV-SITE-B"
SITE_ADMIN_EMAIL = "site.admin.a@lazypay.in"

OFFICE_LOCATIONS = [
    ("Bangalore Office", "BLR", "Bangalore"),
    ("Gurgaon Office", "GGN", "Gurgaon"),
    ("Noida Office", "NOI", "Noida"),
    ("Mumbai Office", "MUM", "Mumbai"),
    ("Pune Office", "PUN", "Pune"),
]

DEFAULT_TIMEZONE = "Asia/Kolkata"

DEV_USERS = [
    ("headadmin@vms.local", "Head Admin", AdminRole.HEAD_ADMIN, "BLR"),
    ("security.blr@vms.local", "Security BLR", AdminRole.SECURITY, "BLR"),
    ("siteadmin.blr@vms.local", "Site Admin BLR", AdminRole.SITE_ADMIN, "BLR"),
    ("security.mum@vms.local", "Security MUM", AdminRole.SECURITY, "MUM"),
    ("siteadmin.mum@vms.local", "Site Admin MUM", AdminRole.SITE_ADMIN, "MUM"),
]

VISITOR_TYPES = [
    ("Business Visitor", "BUSINESS"),
    ("Partner", "PARTNER"),
    ("Vendor", "VENDOR"),
    ("Contractor", "CONTRACTOR"),
    ("Interview Candidate", "INTERVIEW"),
    ("Service / Maintenance", "SERVICE"),
    ("Delivery / Courier", "DELIVERY"),
    ("Event / Group", "EVENT"),
    ("VIP", "VIP"),
    ("Other", "OTHER"),
]

DEV_HOSTS = [
    ("Amit Kumar", "Engineering"),
    ("Priya Sharma", "Human Resources"),
    ("Rajesh Patel", "Operations"),
]

COMPLIANCE_REQUIREMENT_SEEDS = [
    ("Vendor Authorization Letter", "VENDOR_AUTH_LETTER", "COMPANY", True, True),
    ("Insurance / Liability Certificate", "INSURANCE_CERT", "COMPANY", True, True),
    ("Safety Training Certificate", "SAFETY_TRAINING", "VISITOR", True, True),
    ("Work Authorization", "WORK_AUTH", "VISITOR", False, False),
]


def _ensure_compliance_requirements(db: Session) -> None:
    for name, code, owner, mandatory, validity in COMPLIANCE_REQUIREMENT_SEEDS:
        existing = db.query(ComplianceRequirement).filter(ComplianceRequirement.code == code).first()
        if existing:
            continue
        db.add(
            ComplianceRequirement(
                name=name,
                code=code,
                description=name,
                visitor_type_id=None,
                scope_type="GLOBAL",
                document_owner_type=owner,
                document_required=True,
                validity_required=validity,
                safety_acknowledgement_required=False,
                is_mandatory=mandatory,
                is_active=True,
                expiry_warning_days=30,
            )
        )


def _ensure_office_locations(db: Session) -> dict[str, Location]:
    by_code: dict[str, Location] = {}
    for name, code, city in OFFICE_LOCATIONS:
        loc = db.query(Location).filter(Location.code == code).first()
        if not loc:
            loc = Location(
                name=name,
                code=code,
                city=city,
                timezone=DEFAULT_TIMEZONE,
                is_active=True,
                is_development_seed=False,
                registration_enabled=True,
                public_registration_token=generate_public_token(),
            )
            db.add(loc)
            db.flush()
        else:
            if not loc.city:
                loc.city = city
            if not loc.timezone:
                loc.timezone = DEFAULT_TIMEZONE
            if not loc.public_registration_token:
                loc.public_registration_token = generate_public_token()
            loc.registration_enabled = True
            loc.is_development_seed = False
        by_code[code] = loc
    return by_code


def _ensure_visitor_types(db: Session) -> None:
    for name, code in VISITOR_TYPES:
        existing = db.query(VisitorType).filter(VisitorType.code == code).first()
        if not existing:
            requires = code in ("VENDOR", "CONTRACTOR", "SERVICE")
            po_req = code in ("VENDOR", "CONTRACTOR")
            db.add(
                VisitorType(
                    name=name,
                    code=code,
                    is_active=True,
                    requires_vendor_compliance=requires,
                    po_reference_required=po_req,
                )
            )
        else:
            if code in ("VENDOR", "CONTRACTOR", "SERVICE"):
                existing.requires_vendor_compliance = True
            if code in ("VENDOR", "CONTRACTOR"):
                existing.po_reference_required = True


def _ensure_default_retention_policies(db: Session) -> None:
    from app.application.data_retention_service import seed_default_retention_policies

    seed_default_retention_policies(db)


def _ensure_location_access_configurations(db: Session) -> None:
    for loc in db.query(Location).filter(Location.is_active.is_(True)).all():
        existing_cfg = (
            db.query(LocationAccessConfiguration)
            .filter(LocationAccessConfiguration.location_id == loc.id)
            .first()
        )
        if not existing_cfg:
            db.add(
                LocationAccessConfiguration(
                    location_id=loc.id,
                    access_control_enabled=False,
                    provider_key="disabled",
                    credential_grace_minutes=30,
                    max_credential_duration_minutes=720,
                    is_active=True,
                )
            )


class OwnerEmailConflictError(Exception):
    """Both legacy and new owner emails exist as separate accounts."""

    code = "OWNER_EMAIL_CONFLICT"


def reconcile_owner_identity(db: Session) -> Optional[AdminUser]:
    """Migrate legacy owner email to OWNER_EMAIL or return existing owner row."""
    new_owner = db.query(AdminUser).filter(AdminUser.email.ilike(OWNER_EMAIL)).first()
    legacy_owner = db.query(AdminUser).filter(AdminUser.email.ilike(LEGACY_OWNER_EMAIL)).first()

    if legacy_owner and new_owner and legacy_owner.id != new_owner.id:
        raise OwnerEmailConflictError(
            "OWNER_EMAIL_CONFLICT: both legacy and new owner emails exist as separate accounts."
        )

    if new_owner and new_owner.is_owner:
        new_owner.email = OWNER_EMAIL
        new_owner.role = AdminRole.GLOBAL_ADMIN.value
        new_owner.is_owner = True
        new_owner.is_active = True
        from app.application.vms_native_auth_service import ensure_vms_native_auth

        ensure_vms_native_auth(db, new_owner)
        db.flush()
        return new_owner

    if legacy_owner and legacy_owner.is_owner:
        previous_email = legacy_owner.email
        if previous_email.lower() != OWNER_EMAIL.lower():
            legacy_owner.email = OWNER_EMAIL
            db.flush()
            audit = AuditService(db)
            audit.record(
                action="OWNER_EMAIL_UPDATED",
                entity_type="admin_user",
                entity_id=str(legacy_owner.id),
                actor_email=OWNER_EMAIL,
                before_value={"email": previous_email},
                after_value={"email": OWNER_EMAIL, "role": legacy_owner.role, "is_owner": True},
            )
        legacy_owner.role = AdminRole.GLOBAL_ADMIN.value
        legacy_owner.is_owner = True
        legacy_owner.is_active = True
        from app.application.vms_native_auth_service import ensure_vms_native_auth

        ensure_vms_native_auth(db, legacy_owner)
        db.flush()
        return legacy_owner

    if new_owner and not new_owner.is_owner:
        raise OwnerEmailConflictError(
            "OWNER_EMAIL_CONFLICT: target owner email exists but is not marked as owner."
        )

    return None


def ensure_permanent_owner(db: Session) -> AdminUser:
    """Reconcile owner identity and direct-auth settings (production-safe)."""
    owner = reconcile_owner_identity(db)
    if owner is None:
        owner = db.query(AdminUser).filter(AdminUser.email.ilike(OWNER_EMAIL)).first()
    if not owner:
        owner = AdminUser(
            email=OWNER_EMAIL,
            display_name="Sheru Bohra",
            role=AdminRole.GLOBAL_ADMIN.value,
            is_owner=True,
            is_active=True,
            auth_provider="vms_native",
        )
        db.add(owner)
        db.flush()

        audit = AuditService(db)
        audit.record(
            action="bootstrap.owner_created",
            entity_type="admin_user",
            entity_id=str(owner.id),
            actor_email=OWNER_EMAIL,
            after_value={"email": OWNER_EMAIL, "role": AdminRole.GLOBAL_ADMIN.value, "is_owner": True},
        )

    from app.application.vms_native_auth_service import ensure_vms_native_auth

    ensure_vms_native_auth(db, owner)
    db.flush()
    return owner


def bootstrap_application_data(db: Session) -> None:
    """Production-safe bootstrap: owner, master configuration, office locations only."""
    ensure_permanent_owner(db)
    _ensure_office_locations(db)
    _ensure_visitor_types(db)
    _ensure_compliance_requirements(db)
    _ensure_default_retention_policies(db)
    _ensure_location_access_configurations(db)
    db.commit()


def bootstrap_development_data(db: Session) -> None:
    """Test-only bootstrap with demo users, dev locations, and sample hosts."""
    bootstrap_application_data(db)

    office_locations = _ensure_office_locations(db)

    location = db.query(Location).filter(Location.code == DEV_LOCATION_CODE).first()
    if not location:
        location = Location(
            name="Development Main Office",
            code=DEV_LOCATION_CODE,
            city="Development",
            timezone=DEFAULT_TIMEZONE,
            is_active=True,
            is_development_seed=True,
            registration_enabled=True,
        )
        db.add(location)
        db.flush()
    if not location.public_registration_token:
        location.public_registration_token = generate_public_token()
        location.registration_enabled = True
    if not location.timezone:
        location.timezone = DEFAULT_TIMEZONE

    location_b = db.query(Location).filter(Location.code == DEV_LOCATION_B_CODE).first()
    if not location_b:
        location_b = Location(
            name="Development Site B",
            code=DEV_LOCATION_B_CODE,
            city="Development",
            timezone=DEFAULT_TIMEZONE,
            is_active=True,
            is_development_seed=True,
            registration_enabled=True,
            public_registration_token=generate_public_token(),
        )
        db.add(location_b)
        db.flush()

    db.flush()

    blr = office_locations.get("BLR")
    for name, department in DEV_HOSTS:
        existing = db.query(Host).filter(Host.name == name, Host.is_development_seed.is_(True)).first()
        if not existing:
            host = Host(
                name=name,
                email=f"{name.split()[0].lower()}.dev@lazypay.in",
                department=department,
                is_active=True,
                is_development_seed=True,
            )
            db.add(host)
            db.flush()
            db.add(HostLocationAssignment(host_id=host.id, location_id=location.id))
            if blr:
                db.add(HostLocationAssignment(host_id=host.id, location_id=blr.id))
        else:
            if blr:
                has_blr = (
                    db.query(HostLocationAssignment)
                    .filter(
                        HostLocationAssignment.host_id == existing.id,
                        HostLocationAssignment.location_id == blr.id,
                    )
                    .first()
                )
                if not has_blr:
                    db.add(HostLocationAssignment(host_id=existing.id, location_id=blr.id))

    site_admin = db.query(AdminUser).filter(AdminUser.email == SITE_ADMIN_EMAIL).first()
    if not site_admin:
        site_admin = AdminUser(
            email=SITE_ADMIN_EMAIL,
            display_name="Site Admin A",
            role=AdminRole.SITE_ADMIN.value,
            is_owner=False,
            is_active=True,
            auth_provider="vms_native",
            force_password_change=True,
        )
        db.add(site_admin)
        db.flush()
        db.add(UserLocationAssignment(admin_user_id=site_admin.id, location_id=location.id))

    for email, display_name, role, loc_code in DEV_USERS:
        user = db.query(AdminUser).filter(AdminUser.email == email).first()
        loc = office_locations.get(loc_code)
        if not loc:
            continue
        if not user:
            user = AdminUser(
                email=email,
                display_name=display_name,
                role=role.value,
                is_owner=False,
                is_active=True,
                auth_provider="vms_native",
                force_password_change=True,
            )
            db.add(user)
            db.flush()
        assignment = (
            db.query(UserLocationAssignment)
            .filter(
                UserLocationAssignment.admin_user_id == user.id,
                UserLocationAssignment.location_id == loc.id,
            )
            .first()
        )
        if not assignment:
            db.add(UserLocationAssignment(admin_user_id=user.id, location_id=loc.id))

    db.commit()


def ensure_owner_protected(user: AdminUser, updates: dict) -> None:
    if not user.is_owner:
        return
    if updates.get("is_owner") is False:
        raise ValueError("Cannot remove owner status from the permanent owner account.")
    if updates.get("role") and updates["role"] != AdminRole.GLOBAL_ADMIN.value:
        raise ValueError("Cannot downgrade role of the permanent owner account.")
    if updates.get("is_active") is False:
        raise ValueError("Cannot deactivate the permanent owner account.")
    if updates.get("email") and updates["email"] != OWNER_EMAIL:
        raise ValueError("Cannot change email of the permanent owner account.")


def is_owner_email(email: str) -> bool:
    return email.lower() == OWNER_EMAIL.lower()
