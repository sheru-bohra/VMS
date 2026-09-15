"""Deterministic vendor/compliance evaluation engine."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import case
from sqlalchemy.orm import Session, joinedload

from app.application.audit_service import AuditService
from app.application.identity_normalization import normalize_company
from app.core.config import settings
from app.domain.enums import (
    ComplianceDocumentOwnerType,
    ComplianceDocumentStatus,
    ComplianceScopeType,
    ComplianceStatus,
    VisitSource,
)
from app.domain.models import (
    ComplianceDocument,
    ComplianceEvaluation,
    ComplianceRequirement,
    VendorCompany,
    VendorVisitDetails,
    Visit,
    Visitor,
    VisitorType,
)


class ComplianceError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 403):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def visitor_type_requires_compliance(db: Session, visitor_type_id: Optional[int]) -> bool:
    if not visitor_type_id:
        return False
    vt = db.query(VisitorType).filter(VisitorType.id == visitor_type_id).first()
    return bool(vt and vt.requires_vendor_compliance)


def get_evaluation_datetime(visit: Visit) -> datetime:
    if visit.scheduled_start:
        return _as_utc(visit.scheduled_start)
    if visit.expected_arrival:
        return _as_utc(visit.expected_arrival)
    return _now()


def load_applicable_requirements(
    db: Session,
    visitor_type_id: int,
    location_id: int,
) -> List[ComplianceRequirement]:
    rows = db.query(ComplianceRequirement).filter(
        ComplianceRequirement.is_active.is_(True),
        (ComplianceRequirement.visitor_type_id.is_(None))
        | (ComplianceRequirement.visitor_type_id == visitor_type_id),
    ).all()
    applicable: List[ComplianceRequirement] = []
    for req in rows:
        if req.scope_type == ComplianceScopeType.GLOBAL.value or req.location_id is None:
            applicable.append(req)
        elif req.scope_type == ComplianceScopeType.LOCATION.value and req.location_id == location_id:
            applicable.append(req)
    return applicable


def _find_current_document(
    db: Session,
    requirement: ComplianceRequirement,
    vendor_company_id: Optional[int],
    visitor_id: Optional[int],
) -> Optional[ComplianceDocument]:
    query = db.query(ComplianceDocument).filter(
        ComplianceDocument.requirement_id == requirement.id,
        ComplianceDocument.status != ComplianceDocumentStatus.REJECTED.value,
    )
    if requirement.document_owner_type == ComplianceDocumentOwnerType.COMPANY.value:
        if not vendor_company_id:
            return None
        query = query.filter(ComplianceDocument.vendor_company_id == vendor_company_id)
    else:
        if not visitor_id:
            return None
        query = query.filter(ComplianceDocument.visitor_id == visitor_id)
    status_rank = case(
        (ComplianceDocument.status == ComplianceDocumentStatus.VALID.value, 0),
        (ComplianceDocument.status == ComplianceDocumentStatus.PENDING_VERIFICATION.value, 1),
        (ComplianceDocument.status == ComplianceDocumentStatus.EXPIRING.value, 2),
        (ComplianceDocument.status == ComplianceDocumentStatus.EXPIRED.value, 3),
        else_=4,
    )
    return query.order_by(status_rank, ComplianceDocument.uploaded_at.desc()).first()


def _document_usability(
    doc: Optional[ComplianceDocument],
    requirement: ComplianceRequirement,
    evaluation_dt: datetime,
) -> Tuple[str, Optional[str]]:
    if not doc:
        return "missing", None
    if doc.status == ComplianceDocumentStatus.REJECTED.value:
        return "rejected", doc.file_name
    if doc.status == ComplianceDocumentStatus.PENDING_VERIFICATION.value:
        return "pending", doc.file_name
    if requirement.validity_required and doc.valid_until:
        until = _as_utc(doc.valid_until)
        if until < evaluation_dt:
            return "expired", doc.file_name
        warning_end = evaluation_dt + timedelta(days=requirement.expiry_warning_days)
        if until <= warning_end:
            return "expiring", doc.file_name
    if doc.status == ComplianceDocumentStatus.EXPIRED.value:
        return "expired", doc.file_name
    return "valid", doc.file_name


def _registration_meta(visit: Visit) -> Dict[str, Any]:
    meta = visit.registration_metadata_json
    return meta if isinstance(meta, dict) else {}


def _resolve_vendor_company_id(visit: Visit) -> Optional[int]:
    details = visit.vendor_visit_details
    if details and details.vendor_company_id:
        return details.vendor_company_id
    vendor_id = _registration_meta(visit).get("vendor_company_id")
    if vendor_id:
        try:
            return int(vendor_id)
        except (TypeError, ValueError):
            return None
    return None


def _resolve_po_reference(visit: Visit) -> Optional[str]:
    details = visit.vendor_visit_details
    if details and details.po_work_order_reference and details.po_work_order_reference.strip():
        return details.po_work_order_reference.strip()
    po = _registration_meta(visit).get("po_work_order_reference")
    if po and str(po).strip():
        return str(po).strip()
    return None


def _resolve_safety_acknowledged(visit: Visit) -> bool:
    details = visit.vendor_visit_details
    if details and details.safety_acknowledged:
        return True
    meta = _registration_meta(visit)
    return bool(meta.get("safety_induction_completed") or meta.get("safety_acknowledged"))


def _po_satisfied_at_registration(visit: Visit, visitor_type: Optional[VisitorType]) -> bool:
    """Staff registration already validated PO when no vendor master link was created."""
    if visit.source != VisitSource.ADVANCE_REGISTRATION.value:
        return False
    if _resolve_vendor_company_id(visit):
        return False
    return bool(visitor_type and visitor_type.po_reference_required)


def _company_requirement_applicable(requirement: ComplianceRequirement, vendor_company_id: Optional[int]) -> bool:
    if requirement.document_owner_type != ComplianceDocumentOwnerType.COMPANY.value:
        return True
    return vendor_company_id is not None


def _registration_satisfies_requirement(requirement: ComplianceRequirement, visit: Visit) -> bool:
    if requirement.code == "SAFETY_TRAINING":
        return _resolve_safety_acknowledged(visit)
    return False


def _blocker_messages_from_signals(signals: List[str]) -> List[str]:
    messages: List[str] = []
    for signal in signals:
        if signal.startswith("Missing: "):
            messages.append(f"{signal[9:]} is incomplete")
        elif signal.startswith("Expired: "):
            messages.append(f"{signal[9:]} has expired")
        elif signal.startswith("Pending verification: "):
            messages.append(f"{signal[22:]} is pending verification")
        elif signal.startswith("Expiring before visit: "):
            messages.append(f"{signal[23:]} is expiring before the visit date")
    return messages


def _format_approval_block_message(signals: List[str]) -> str:
    blockers = _blocker_messages_from_signals(signals)
    if not blockers:
        return "This visit does not meet compliance requirements and cannot be approved."
    if len(blockers) == 1:
        return f"Approval blocked — {blockers[0]}."
    joined = "\n• ".join(blockers)
    return f"Approval blocked — {len(blockers)} compliance requirements need attention:\n• {joined}"


def evaluate_visit_compliance(db: Session, visit_id: int, trigger: str = "manual") -> ComplianceEvaluation:
    visit = (
        db.query(Visit)
        .options(joinedload(Visit.visitor), joinedload(Visit.vendor_visit_details))
        .filter(Visit.id == visit_id)
        .first()
    )
    if not visit or not visit.visitor:
        raise ComplianceError("not_found", "Visit not found.", 404)

    visitor = visit.visitor
    if not visitor_type_requires_compliance(db, visitor.visitor_type_id):
        visit.compliance_status = ComplianceStatus.COMPLIANT.value
        evaluation = ComplianceEvaluation(
            visit_id=visit.id,
            status=ComplianceStatus.COMPLIANT.value,
            evaluated_at=_now(),
            evaluation_date=get_evaluation_datetime(visit),
            reason_summary="No vendor compliance required for visitor type.",
            signals_json=json.dumps([]),
            trigger=trigger,
        )
        db.add(evaluation)
        return evaluation

    evaluation_dt = get_evaluation_datetime(visit)
    vendor_company_id = _resolve_vendor_company_id(visit)

    requirements = load_applicable_requirements(db, visitor.visitor_type_id, visit.location_id)
    signals: List[str] = []
    missing: List[str] = []
    expired: List[str] = []
    expiring: List[str] = []
    pending: List[str] = []

    vt = db.query(VisitorType).filter(VisitorType.id == visitor.visitor_type_id).first()
    if vt and vt.po_reference_required:
        po_reference = _resolve_po_reference(visit)
        if not po_reference and not _po_satisfied_at_registration(visit, vt):
            missing.append("PO / Work Order Reference")
            signals.append("Missing: PO / Work Order Reference")

    safety_required = visitor_type_requires_compliance(db, visitor.visitor_type_id)
    if safety_required and not _resolve_safety_acknowledged(visit):
        missing.append("Safety acknowledgement")
        signals.append("Missing: Safety acknowledgement")

    for req in requirements:
        if not req.document_required:
            continue
        if not _company_requirement_applicable(req, vendor_company_id):
            signals.append(f"Not applicable: {req.name} (no vendor company master link)")
            continue
        if _registration_satisfies_requirement(req, visit):
            signals.append(f"Valid: {req.name} (registration)")
            continue
        doc = _find_current_document(db, req, vendor_company_id, visitor.id)
        usability, name = _document_usability(doc, req, evaluation_dt)
        if usability == "missing" and req.is_mandatory:
            missing.append(req.name)
            signals.append(f"Missing: {req.name}")
        elif usability == "pending":
            pending.append(req.name)
            signals.append(f"Pending verification: {req.name}")
        elif usability == "expired":
            expired.append(req.name)
            signals.append(f"Expired: {req.name}")
        elif usability == "expiring":
            expiring.append(req.name)
            signals.append(f"Expiring before visit: {req.name}")
        elif usability == "valid" and doc:
            signals.append(f"Valid: {req.name} (reusable)")

    status = ComplianceStatus.COMPLIANT
    reason = "All compliance requirements satisfied."

    if missing or expired:
        status = ComplianceStatus.NON_COMPLIANT
        reason = "Compliance requirements not satisfied."
    elif pending:
        status = ComplianceStatus.REVIEW_REQUIRED
        reason = "Compliance documents require verification."
    elif expiring:
        status = ComplianceStatus.EXPIRING
        reason = "Some documents are expiring before the visit date."

    visit.compliance_status = status.value
    now = _now()
    evaluation = ComplianceEvaluation(
        visit_id=visit.id,
        status=status.value,
        evaluated_at=now,
        evaluation_date=evaluation_dt,
        reason_summary=reason,
        signals_json=json.dumps(signals),
        trigger=trigger,
    )
    db.add(evaluation)
    db.flush()

    audit = AuditService(db)
    audit.record(
        action="COMPLIANCE_EVALUATED",
        entity_type="visit",
        entity_id=str(visit.id),
        location_id=visit.location_id,
        after_value={"status": status.value, "trigger": trigger},
    )
    if status == ComplianceStatus.REVIEW_REQUIRED:
        audit.record(
            action="COMPLIANCE_REVIEW_REQUIRED",
            entity_type="visit",
            entity_id=str(visit.id),
            location_id=visit.location_id,
        )

    return evaluation


def ensure_allows_approval(db: Session, visit_id: int) -> None:
    evaluation = evaluate_visit_compliance(db, visit_id, trigger="approval")
    visit = db.query(Visit).filter(Visit.id == visit_id).first()
    if not visit:
        raise ComplianceError("not_found", "Visit not found.", 404)
    status = visit.compliance_status or ComplianceStatus.COMPLIANT.value
    signals: List[str] = []
    if evaluation.signals_json:
        try:
            signals = json.loads(evaluation.signals_json)
        except json.JSONDecodeError:
            signals = []
    if status == ComplianceStatus.NON_COMPLIANT.value:
        raise ComplianceError(
            "COMPLIANCE_NON_COMPLIANT",
            _format_approval_block_message(signals),
            403,
        )
    if status == ComplianceStatus.REVIEW_REQUIRED.value:
        raise ComplianceError(
            "COMPLIANCE_REVIEW_REQUIRED",
            _format_approval_block_message(signals)
            if signals
            else "Compliance review must be completed before this visitor can be approved.",
            403,
        )


def ensure_allows_checkin(db: Session, visit_id: int) -> None:
    evaluate_visit_compliance(db, visit_id, trigger="check_in")
    visit = db.query(Visit).filter(Visit.id == visit_id).first()
    if not visit:
        raise ComplianceError("not_found", "Visit not found.", 404)
    status = visit.compliance_status
    if status == ComplianceStatus.NON_COMPLIANT.value:
        raise ComplianceError(
            "COMPLIANCE_NON_COMPLIANT",
            "Check-in blocked: compliance requirements are not satisfied.",
            403,
        )
    if status == ComplianceStatus.REVIEW_REQUIRED.value:
        raise ComplianceError(
            "COMPLIANCE_REVIEW_REQUIRED",
            "Compliance review must be completed before check-in.",
            403,
        )


def compliance_summary_for_visit(db: Session, visit_id: int) -> Dict[str, Any]:
    visit = (
        db.query(Visit)
        .options(joinedload(Visit.visitor), joinedload(Visit.vendor_visit_details))
        .filter(Visit.id == visit_id)
        .first()
    )
    if not visit:
        return {"compliance_status": ComplianceStatus.COMPLIANT.value}
    latest = (
        db.query(ComplianceEvaluation)
        .filter(ComplianceEvaluation.visit_id == visit_id)
        .order_by(ComplianceEvaluation.evaluated_at.desc())
        .first()
    )
    signals: List[str] = []
    if latest and latest.signals_json:
        try:
            signals = json.loads(latest.signals_json)
        except json.JSONDecodeError:
            signals = []
    return {
        "compliance_status": visit.compliance_status,
        "reason_summary": latest.reason_summary if latest else None,
        "signals": signals,
        "evaluated_at": latest.evaluated_at.isoformat() if latest and latest.evaluated_at else None,
    }


def find_duplicate_vendor_companies(db: Session, name: str, threshold: int = 85) -> List[VendorCompany]:
    from app.application.identity_normalization import name_similarity

    norm = normalize_company(name) or ""
    if not norm:
        return []
    candidates = db.query(VendorCompany).filter(VendorCompany.is_active.is_(True)).all()
    matches: List[VendorCompany] = []
    for c in candidates:
        if name_similarity(norm, c.normalized_name) >= threshold:
            matches.append(c)
    return matches
