"""Deterministic visitor-type policy for staff Register Visitor workflow."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.domain.models import VisitorType

WORKSITE_CODES = frozenset({"VENDOR", "CONTRACTOR", "SERVICE"})


@dataclass(frozen=True)
class RegisterVisitorPolicy:
    company_required: bool
    email_required: bool
    host_required: bool
    govt_id_required: bool
    signature_required: bool
    po_work_order_required: bool
    work_purpose_required: bool
    safety_induction_required: bool


def get_register_visitor_policy(visitor_type: VisitorType) -> RegisterVisitorPolicy:
    code = visitor_type.code
    requires_vendor = visitor_type.requires_vendor_compliance
    po_required = visitor_type.po_reference_required or code == "SERVICE"

    if code == "BUSINESS":
        return RegisterVisitorPolicy(True, False, True, False, False, False, False, False)
    if code == "PARTNER":
        return RegisterVisitorPolicy(True, False, True, False, False, False, False, False)
    if code == "VIP":
        return RegisterVisitorPolicy(False, False, True, False, False, False, False, False)
    if code == "INTERVIEW":
        return RegisterVisitorPolicy(False, True, True, False, False, False, False, False)
    if code == "DELIVERY":
        return RegisterVisitorPolicy(False, False, False, False, False, False, False, False)
    if code in ("EVENT", "OTHER"):
        return RegisterVisitorPolicy(False, False, True, False, False, False, False, False)
    if code == "VENDOR":
        return RegisterVisitorPolicy(
            True, False, True, True, True, po_required, True, requires_vendor
        )
    if code in ("CONTRACTOR", "SERVICE"):
        return RegisterVisitorPolicy(
            True, False, True, True, True, po_required, True, True
        )
    return RegisterVisitorPolicy(False, False, True, False, False, False, False, False)


def validate_email_format(email: str) -> bool:
    from app.application.registration_service import _EMAIL_RE

    return bool(_EMAIL_RE.match(email.strip()))


def validate_register_fields(
    policy: RegisterVisitorPolicy,
    *,
    email: Optional[str],
    company: Optional[str],
    host_id: Optional[int],
    govt_id_type: Optional[str],
    govt_id_number: Optional[str],
    signature_storage_key: Optional[str],
    work_purpose: Optional[str],
    po_work_order_reference: Optional[str],
    safety_acknowledged: bool,
    safety_induction_completed: bool,
) -> None:
    from app.application.invitation_service import InvitationError

    company_val = (company or "").strip()
    if policy.company_required and not company_val:
        raise InvitationError("company_required", "Company name is required.")

    email_val = (email or "").strip()
    if policy.email_required and not email_val:
        raise InvitationError("email_required", "Email is required.")
    if email_val and not validate_email_format(email_val):
        raise InvitationError("invalid_email", "Enter a valid email address.")

    if policy.host_required and not host_id:
        raise InvitationError("host_required", "Host is required.")

    if policy.govt_id_required:
        if not govt_id_type or not (govt_id_number and govt_id_number.strip()):
            raise InvitationError(
                "govt_id_required", "Government ID type and number are required."
            )

    if policy.signature_required and not signature_storage_key:
        raise InvitationError("signature_required", "Signature is required.")

    if policy.work_purpose_required and not (work_purpose and work_purpose.strip()):
        raise InvitationError("work_purpose_required", "Work purpose is required.")

    if policy.po_work_order_required and not (
        po_work_order_reference and po_work_order_reference.strip()
    ):
        raise InvitationError("po_required", "PO / Work Order reference is required.")

    if policy.safety_induction_required and not (
        safety_acknowledged or safety_induction_completed
    ):
        raise InvitationError("safety_required", "Safety acknowledgement is required.")
