"""Compliance document upload and verification."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, BinaryIO, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.application.audit_service import AuditService
from app.application.auth_service import AuthContext
from app.application.compliance_service import evaluate_visit_compliance
from app.application.document_storage import document_storage, DocumentStorageError
from app.application.site_scope_service import can_access_location
from app.domain.enums import (
    ComplianceDocumentOwnerType,
    ComplianceDocumentStatus,
    Permission,
    role_has_permission,
)
from app.domain.models import AdminUser, ComplianceDocument, ComplianceRequirement, VendorCompany, Visit


class ComplianceDocumentError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _require_upload(ctx: AuthContext) -> None:
    if not role_has_permission(ctx.role, Permission.COMPLIANCE_VERIFY):
        raise ComplianceDocumentError("forbidden", "Permission denied.", 403)


def _require_verify(ctx: AuthContext) -> None:
    if not role_has_permission(ctx.role, Permission.COMPLIANCE_VERIFY):
        raise ComplianceDocumentError("forbidden", "Permission denied.", 403)


def _require_download(ctx: AuthContext) -> None:
    if not role_has_permission(ctx.role, Permission.COMPLIANCE_DOCUMENT_DOWNLOAD):
        raise ComplianceDocumentError("forbidden", "Permission denied.", 403)


def _build_doc_dict(doc: ComplianceDocument, requirement: ComplianceRequirement, db: Optional[Session] = None) -> Dict[str, Any]:
    verified_by_name = None
    if doc.verified_by_user_id and db:
        user = db.query(AdminUser).filter(AdminUser.id == doc.verified_by_user_id).first()
        verified_by_name = user.display_name if user else None
    return {
        "id": doc.id,
        "requirement_id": doc.requirement_id,
        "requirement_code": requirement.code,
        "requirement_name": requirement.name,
        "visitor_id": doc.visitor_id,
        "vendor_company_id": doc.vendor_company_id,
        "file_name": doc.file_name,
        "mime_type": doc.mime_type,
        "file_size_bytes": doc.file_size_bytes,
        "status": doc.status,
        "valid_from": doc.valid_from.isoformat() if doc.valid_from else None,
        "valid_until": doc.valid_until.isoformat() if doc.valid_until else None,
        "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
        "verified_at": doc.verified_at.isoformat() if doc.verified_at else None,
        "verified_by_user_id": doc.verified_by_user_id,
        "verified_by_name": verified_by_name,
        "rejection_comment": doc.rejection_comment,
        "scan_status": doc.scan_status,
        "supersedes_id": doc.supersedes_id,
        "is_current": False,
    }


def list_documents_for_owner(
    db: Session,
    requirement_id: int,
    vendor_company_id: Optional[int] = None,
    visitor_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    req = db.query(ComplianceRequirement).filter(ComplianceRequirement.id == requirement_id).first()
    if not req:
        return []
    query = db.query(ComplianceDocument).filter(ComplianceDocument.requirement_id == requirement_id)
    if req.document_owner_type == ComplianceDocumentOwnerType.COMPANY.value and vendor_company_id:
        query = query.filter(ComplianceDocument.vendor_company_id == vendor_company_id)
    elif visitor_id:
        query = query.filter(ComplianceDocument.visitor_id == visitor_id)
    else:
        return []
    docs = query.order_by(ComplianceDocument.uploaded_at.desc()).all()
    return [_build_doc_dict(d, req, db) for d in docs]


def upload_document(
    db: Session,
    ctx: AuthContext,
    requirement_id: int,
    file_stream: BinaryIO,
    file_name: str,
    mime_type: Optional[str],
    size_bytes: int,
    vendor_company_id: Optional[int] = None,
    visitor_id: Optional[int] = None,
    valid_from: Optional[datetime] = None,
    valid_until: Optional[datetime] = None,
    visit_id: Optional[int] = None,
    supersedes_id: Optional[int] = None,
) -> Dict[str, Any]:
    _require_upload(ctx)
    req = db.query(ComplianceRequirement).filter(ComplianceRequirement.id == requirement_id).first()
    if not req or not req.is_active:
        raise ComplianceDocumentError("invalid_requirement", "Compliance requirement not found.")
    if req.document_owner_type == ComplianceDocumentOwnerType.COMPANY.value:
        if not vendor_company_id:
            raise ComplianceDocumentError("vendor_required", "Vendor company is required for this document.")
        company = db.query(VendorCompany).filter(VendorCompany.id == vendor_company_id).first()
        if not company or not company.is_active:
            raise ComplianceDocumentError("invalid_vendor", "Vendor company not found or inactive.")
    else:
        if not visitor_id:
            raise ComplianceDocumentError("visitor_required", "Visitor is required for this document.")
    if visit_id:
        visit = db.query(Visit).filter(Visit.id == visit_id).first()
        if visit and not can_access_location(ctx, visit.location_id):
            raise ComplianceDocumentError("forbidden", "Permission denied.", 403)

    try:
        storage_key, display_name, scan_status, encrypted, enc_version = document_storage.save(
            file_stream, file_name, mime_type, size_bytes
        )
    except DocumentStorageError as exc:
        raise ComplianceDocumentError(exc.code, exc.message)

    now = datetime.now(timezone.utc)
    if supersedes_id:
        superseded_doc = db.query(ComplianceDocument).filter(ComplianceDocument.id == supersedes_id).first()
        if not superseded_doc or superseded_doc.requirement_id != requirement_id:
            raise ComplianceDocumentError("invalid_supersedes", "Previous document not found for this requirement.")
    doc = ComplianceDocument(
        requirement_id=requirement_id,
        visitor_id=visitor_id,
        vendor_company_id=vendor_company_id,
        file_name=display_name,
        storage_key=storage_key,
        mime_type=mime_type,
        file_size_bytes=size_bytes,
        uploaded_by_actor_type="ADMIN_USER",
        uploaded_by_user_id=ctx.user_id,
        valid_from=_as_utc(valid_from) if valid_from else None,
        valid_until=_as_utc(valid_until) if valid_until else None,
        status=ComplianceDocumentStatus.PENDING_VERIFICATION.value,
        scan_status=scan_status,
        storage_state="STORED",
        encrypted=encrypted,
        encryption_version=enc_version,
        malware_scan_status=scan_status,
        malware_scanned_at=now,
        supersedes_id=supersedes_id,
    )
    db.add(doc)
    db.flush()
    AuditService(db).record(
        action="COMPLIANCE_DOCUMENT_UPLOADED",
        entity_type="compliance_document",
        entity_id=str(doc.id),
        actor_id=ctx.user_id,
        actor_email=ctx.email,
        after_value={"requirement_id": requirement_id, "status": doc.status},
    )
    if supersedes_id:
        AuditService(db).record(
            action="COMPLIANCE_DOCUMENT_RENEWED",
            entity_type="compliance_document",
            entity_id=str(doc.id),
            actor_id=ctx.user_id,
            actor_email=ctx.email,
            after_value={"supersedes_id": supersedes_id},
        )
    if visit_id:
        evaluate_visit_compliance(db, visit_id, trigger="document_upload")
    db.commit()
    return _build_doc_dict(doc, req, db)


def verify_document(db: Session, ctx: AuthContext, document_id: int, visit_id: Optional[int] = None) -> Dict[str, Any]:
    _require_verify(ctx)
    doc = db.query(ComplianceDocument).filter(ComplianceDocument.id == document_id).first()
    if not doc:
        raise ComplianceDocumentError("not_found", "Document not found.", 404)
    if doc.status != ComplianceDocumentStatus.PENDING_VERIFICATION.value:
        raise ComplianceDocumentError(
            "invalid_state",
            "Only pending documents can be verified.",
            409,
        )
    req = db.query(ComplianceRequirement).filter(ComplianceRequirement.id == doc.requirement_id).first()
    now = datetime.now(timezone.utc)
    doc.status = ComplianceDocumentStatus.VALID.value
    if req and req.validity_required and doc.valid_until:
        until = _as_utc(doc.valid_until)
        if until < now:
            doc.status = ComplianceDocumentStatus.EXPIRED.value
    doc.verified_at = now
    doc.verified_by_user_id = ctx.user_id
    AuditService(db).record(
        action="COMPLIANCE_DOCUMENT_VERIFIED",
        entity_type="compliance_document",
        entity_id=str(doc.id),
        actor_id=ctx.user_id,
        actor_email=ctx.email,
    )
    if visit_id:
        evaluate_visit_compliance(db, visit_id, trigger="document_verify")
    db.commit()
    return _build_doc_dict(doc, req, db)


def reject_document(
    db: Session,
    ctx: AuthContext,
    document_id: int,
    comment: str,
    visit_id: Optional[int] = None,
) -> Dict[str, Any]:
    _require_verify(ctx)
    if not comment or not comment.strip():
        raise ComplianceDocumentError("comment_required", "Rejection comment is required.")
    doc = db.query(ComplianceDocument).filter(ComplianceDocument.id == document_id).first()
    if not doc:
        raise ComplianceDocumentError("not_found", "Document not found.", 404)
    if doc.status != ComplianceDocumentStatus.PENDING_VERIFICATION.value:
        raise ComplianceDocumentError(
            "invalid_state",
            "Only pending documents can be rejected.",
            409,
        )
    req = db.query(ComplianceRequirement).filter(ComplianceRequirement.id == doc.requirement_id).first()
    doc.status = ComplianceDocumentStatus.REJECTED.value
    doc.rejection_comment = comment.strip()
    AuditService(db).record(
        action="COMPLIANCE_DOCUMENT_REJECTED",
        entity_type="compliance_document",
        entity_id=str(doc.id),
        actor_id=ctx.user_id,
        actor_email=ctx.email,
    )
    if visit_id:
        evaluate_visit_compliance(db, visit_id, trigger="document_reject")
    db.commit()
    return _build_doc_dict(doc, req, db)


def get_document_download(
    db: Session,
    ctx: AuthContext,
    document_id: int,
) -> Tuple[str, str, bytes]:
    _require_download(ctx)
    doc = db.query(ComplianceDocument).filter(ComplianceDocument.id == document_id).first()
    if not doc:
        raise ComplianceDocumentError("not_found", "Document not found.", 404)
    if doc.storage_state == "PURGED":
        raise ComplianceDocumentError("purged", "Document is no longer available.", 404)
    mime = doc.mime_type or "application/octet-stream"
    if doc.encrypted:
        data = document_storage.read_decrypted(doc.storage_key, True, doc.encryption_version)
        return doc.file_name, mime, data
    path = document_storage.resolve_path(doc.storage_key)
    return doc.file_name, mime, path.read_bytes()
