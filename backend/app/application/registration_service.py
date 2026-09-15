"""Public self-registration service."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import joinedload, Session

from app.application.audit_service import AuditService
from app.domain.enums import VisitStatus
from app.domain.models import Host, HostLocationAssignment, Location, Visitor, VisitorType, Visit

CURRENT_POLICY_VERSION = "1.0"
DUPLICATE_WINDOW_SECONDS = 60
REFERENCE_PREFIX = "VMS"

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class RegistrationError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def normalize_phone(phone: str) -> str:
    return re.sub(r"[^\d+]", "", phone.strip())


def normalize_email(email: str) -> str:
    return email.strip().lower()


def normalize_name(name: str) -> str:
    return " ".join(name.strip().split())


def get_location_by_token(db: Session, token: str) -> Optional[Location]:
    return db.query(Location).filter(
        Location.public_registration_token == token,
        Location.is_active.is_(True),
        Location.registration_enabled.is_(True),
    ).first()


def get_location_by_token_any(db: Session, token: str) -> Optional[Location]:
    return db.query(Location).filter(Location.public_registration_token == token).first()


def generate_registration_reference(db: Session) -> str:
    now = datetime.now(timezone.utc)
    date_part = now.strftime("%d%m%y")
    prefix = f"{REFERENCE_PREFIX}-{date_part}-"
    count_today = db.query(func.count(Visit.id)).filter(
        Visit.registration_reference.like(f"{prefix}%")
    ).scalar() or 0
    seq = count_today + 1
    for attempt in range(100):
        ref = f"{prefix}{seq:04d}"
        exists = db.query(Visit.id).filter(Visit.registration_reference == ref).first()
        if not exists:
            return ref
        seq += 1
    raise RegistrationError("reference_generation_failed", "Unable to generate registration reference.")


def find_duplicate_registration(
    db: Session,
    location_id: int,
    mobile: str,
    email: str,
    host_id: int,
) -> Optional[Visit]:
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=DUPLICATE_WINDOW_SECONDS)
    normalized_mobile = normalize_phone(mobile)
    normalized_email = normalize_email(email)

    visitor_ids = [row[0] for row in db.query(Visitor.id).filter(
        (Visitor.phone == normalized_mobile) | (Visitor.email == normalized_email)
    ).all()]
    if not visitor_ids:
        return None

    return db.query(Visit).options(joinedload(Visit.visitor)).filter(
        Visit.location_id == location_id,
        Visit.visitor_id.in_(visitor_ids),
        Visit.host_id == host_id,
        Visit.status == VisitStatus.PENDING_APPROVAL.value,
        Visit.created_at >= cutoff,
    ).order_by(Visit.created_at.desc()).first()


def validate_host_for_site(db: Session, host_id: int, location_id: int) -> Host:
    host = db.query(Host).filter(Host.id == host_id, Host.is_active.is_(True)).first()
    if not host:
        raise RegistrationError("invalid_host", "Selected host is not available.")
    assignment = db.query(HostLocationAssignment).filter(
        HostLocationAssignment.host_id == host_id,
        HostLocationAssignment.location_id == location_id,
    ).first()
    if not assignment:
        raise RegistrationError("invalid_host", "Selected host is not available at this site.")
    return host


def validate_visitor_type(db: Session, visitor_type_code: str) -> VisitorType:
    vt = db.query(VisitorType).filter(
        VisitorType.code == visitor_type_code,
        VisitorType.is_active.is_(True),
    ).first()
    if not vt:
        raise RegistrationError("invalid_visitor_type", "Invalid visitor type.")
    return vt


def find_or_create_visitor(
    db: Session,
    full_name: str,
    mobile: str,
    email: str,
    company: str,
    visitor_type_id: int,
    audit: AuditService,
    designation: Optional[str] = None,
    address: Optional[str] = None,
) -> Tuple[Visitor, bool]:
    normalized_mobile = normalize_phone(mobile)
    email_provided = bool(email and email.strip())
    normalized_email = normalize_email(email) if email_provided else None
    query = db.query(Visitor).filter(Visitor.phone == normalized_mobile)
    if normalized_email:
        visitor = db.query(Visitor).filter(
            (Visitor.phone == normalized_mobile) | (Visitor.email == normalized_email)
        ).first()
    else:
        visitor = query.first()

    designation_val = designation.strip() if designation else None
    if designation_val and len(designation_val) > 255:
        designation_val = designation_val[:255]
    address_val = address.strip() if address else None
    if address_val and len(address_val) > 2000:
        address_val = address_val[:2000]

    if visitor:
        visitor.full_name = normalize_name(full_name)
        visitor.phone = normalized_mobile
        if normalized_email:
            visitor.email = normalized_email
        visitor.company = company.strip() if company else None
        visitor.visitor_type_id = visitor_type_id
        if designation_val:
            visitor.designation = designation_val
        if address_val:
            visitor.address = address_val
        audit.record(
            action="VISITOR_REUSED",
            entity_type="visitor",
            entity_id=str(visitor.id),
            after_value={"email": normalized_email, "phone": normalized_mobile},
        )
        return visitor, False

    visitor = Visitor(
        full_name=normalize_name(full_name),
        phone=normalized_mobile,
        email=normalized_email,
        company=company.strip() if company else None,
        visitor_type_id=visitor_type_id,
        designation=designation_val,
        address=address_val,
    )
    db.add(visitor)
    db.flush()
    audit.record(
        action="VISITOR_CREATED",
        entity_type="visitor",
        entity_id=str(visitor.id),
        after_value={"email": normalized_email, "phone": normalized_mobile},
    )
    return visitor, True


def create_self_registration(
    db: Session,
    site_token: str,
    visitor_type_code: str,
    full_name: str,
    mobile: str,
    email: str,
    company: str,
    host_id: int,
    purpose: str,
    expected_duration_minutes: int,
    policy_accepted: bool,
) -> Dict[str, Any]:
    if not policy_accepted:
        raise RegistrationError("policy_required", "Visitor policy must be accepted.")

    location = get_location_by_token(db, site_token)
    if not location:
        raise RegistrationError("invalid_site", "This registration link is invalid or no longer active.")

    full_name = normalize_name(full_name)
    if len(full_name) < 2 or len(full_name) > 200:
        raise RegistrationError("invalid_name", "Please enter a valid full name.")

    normalized_mobile = normalize_phone(mobile)
    if len(normalized_mobile) < 7 or len(normalized_mobile) > 20:
        raise RegistrationError("invalid_mobile", "Please enter a valid mobile number.")

    normalized_email = normalize_email(email)
    if not _EMAIL_RE.match(normalized_email) or len(normalized_email) > 255:
        raise RegistrationError("invalid_email", "Please enter a valid email address.")

    company = company.strip()
    if len(company) < 1 or len(company) > 255:
        raise RegistrationError("invalid_company", "Please enter your company name.")

    purpose = purpose.strip()
    if len(purpose) < 2 or len(purpose) > 500:
        raise RegistrationError("invalid_purpose", "Please enter a visit purpose.")

    allowed_durations = {30, 60, 120, 240, 480}
    if expected_duration_minutes not in allowed_durations:
        raise RegistrationError("invalid_duration", "Please select a valid expected duration.")

    visitor_type = validate_visitor_type(db, visitor_type_code)
    host = validate_host_for_site(db, host_id, location.id)

    duplicate = find_duplicate_registration(db, location.id, mobile, email, host_id)
    if duplicate:
        return {
            "registration_reference": duplicate.registration_reference,
            "status": duplicate.status,
            "visitor_name": duplicate.visitor.full_name if duplicate.visitor else full_name,
            "site_name": location.name,
            "duplicate": True,
        }

    audit = AuditService(db)
    visitor, _ = find_or_create_visitor(
        db, full_name, mobile, email, company, visitor_type.id, audit
    )

    now = datetime.now(timezone.utc)
    reference = generate_registration_reference(db)

    visit = Visit(
        visitor_id=visitor.id,
        location_id=location.id,
        status=VisitStatus.PENDING_APPROVAL.value,
        registration_reference=reference,
        host_id=host.id,
        host_name=host.name,
        purpose=purpose,
        expected_duration_minutes=expected_duration_minutes,
        policy_accepted=True,
        policy_accepted_at=now,
        policy_version=CURRENT_POLICY_VERSION,
        source="self_registration",
    )
    db.add(visit)
    db.flush()

    audit.record(
        action="POLICY_ACCEPTED",
        entity_type="visit",
        entity_id=str(visit.id),
        location_id=location.id,
        after_value={"policy_version": CURRENT_POLICY_VERSION},
    )
    audit.record(
        action="PUBLIC_REGISTRATION_CREATED",
        entity_type="visit",
        entity_id=str(visit.id),
        location_id=location.id,
        after_value={
            "reference": reference,
            "status": VisitStatus.PENDING_APPROVAL.value,
            "host_id": host.id,
        },
    )

    from app.application.host_approval_service import maybe_create_for_pending_visit
    maybe_create_for_pending_visit(db, visit.id)

    from app.application.security_screening_service import screen_visit
    screen_visit(db, visit.id, trigger="self_registration")

    from app.application.compliance_service import evaluate_visit_compliance
    evaluate_visit_compliance(db, visit.id, trigger="self_registration")

    db.commit()
    db.refresh(visit)

    from app.application.notification_dispatch_service import dispatch_pending_notifications
    dispatch_pending_notifications(db)

    return {
        "registration_reference": reference,
        "status": visit.status,
        "visitor_name": visitor.full_name,
        "site_name": location.name,
        "duplicate": False,
    }
