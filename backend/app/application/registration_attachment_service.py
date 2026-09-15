"""Secure registration attachment uploads (photo, signature, ID image)."""

from __future__ import annotations

from io import BytesIO
from typing import Any, Dict

from app.application.auth_service import AuthContext
from app.application.document_storage import EncryptedDocumentStorageProvider, DocumentStorageError
from app.domain.enums import Permission, role_has_permission

_ALLOWED_KINDS = frozenset({"photo", "signature", "id_image"})


class RegistrationAttachmentError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _require_upload(ctx: AuthContext) -> None:
    if not role_has_permission(ctx.role, Permission.INVITATION_CREATE):
        raise RegistrationAttachmentError("forbidden", "Permission denied.", 403)


def save_registration_attachment(
    ctx: AuthContext,
    kind: str,
    file_stream: BytesIO,
    file_name: str,
    mime_type: str | None,
    size_bytes: int,
) -> Dict[str, Any]:
    _require_upload(ctx)
    if kind not in _ALLOWED_KINDS:
        raise RegistrationAttachmentError("invalid_kind", "Invalid attachment type.")
    if kind == "photo":
        raise RegistrationAttachmentError(
            "use_visitor_photo",
            "Visitor photos must use the visitor-photo upload endpoint.",
        )

    storage = EncryptedDocumentStorageProvider()
    try:
        storage_key, display_name, stored_mime, scanned, scan_ms = storage.save(
            file_stream, file_name, mime_type, size_bytes
        )
    except DocumentStorageError as exc:
        raise RegistrationAttachmentError(exc.code, exc.message)

    return {
        "storage_key": storage_key,
        "file_name": display_name,
        "kind": kind,
        "mime_type": stored_mime,
        "scanned": scanned,
        "scan_ms": scan_ms,
        "ocr_status": "unavailable",
        "uploaded_by_user_id": ctx.user_id,
    }
