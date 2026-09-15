"""Visitor photo staging, finalization, and protected access."""

from __future__ import annotations

import imghdr
import os
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.orm import Session

from app.application.auth_service import AuthContext
from app.application.file_security_scanner import get_file_security_scanner, ScanResult
from app.application.site_scope_service import can_access_location
from app.application.visitor_media_filename import (
    build_final_filename,
    build_staged_filename,
    sanitize_name_prefix,
)
from app.core.config import settings
from app.domain.enums import Permission, role_has_permission
from app.domain.models import VisitorMedia
from app.infrastructure.local_media_storage import (
    delete_file,
    ensure_photo_dir,
    LocalMediaStorageError,
    read_bytes,
    rename_file,
    write_bytes,
)

_ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
_ALLOWED_MIME = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
_MEDIA_TYPE_PHOTO = "VISITOR_PHOTO"


class VisitorMediaError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _require_upload(ctx: AuthContext) -> None:
    if not role_has_permission(ctx.role, Permission.INVITATION_CREATE):
        raise VisitorMediaError("forbidden", "Permission denied.", 403)


def _require_read(ctx: AuthContext) -> None:
    if not role_has_permission(ctx.role, Permission.VISITOR_READ):
        raise VisitorMediaError("forbidden", "Permission denied.", 403)


def _validate_image(file_name: str, mime_type: str | None, size_bytes: int, raw: bytes) -> Tuple[str, str]:
    max_bytes = settings.visitor_photo_max_mb * 1024 * 1024
    if size_bytes <= 0:
        raise VisitorMediaError("empty_file", "Uploaded file is empty.")
    if size_bytes > max_bytes:
        raise VisitorMediaError("file_too_large", f"Photo exceeds {settings.visitor_photo_max_mb} MB limit.")
    if ".." in file_name or "/" in file_name or "\\" in file_name:
        raise VisitorMediaError("invalid_file_name", "Invalid file name.")

    detected = imghdr.what(None, h=raw[:32])
    ext_map = {"jpeg": "jpg", "png": "png", "webp": "webp"}
    if not detected or detected not in ext_map:
        raise VisitorMediaError("invalid_image", "Unable to decode image. Use JPEG, PNG, or WEBP.")

    ext = f".{ext_map[detected]}"
    if mime_type and mime_type.lower() not in _ALLOWED_MIME:
        raise VisitorMediaError("invalid_mime", "Unsupported image type.")
    stored_mime = {
        "jpg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
    }[ext_map[detected]]
    return ext, stored_mime


def _scan_bytes(raw: bytes) -> None:
    import tempfile
    scanner = get_file_security_scanner()
    fd, path = tempfile.mkstemp(prefix="vphoto_", suffix=".bin")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(raw)
        result = scanner.scan_file(path)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    if result == ScanResult.INFECTED:
        raise VisitorMediaError("scan_failed", "File did not pass security scan.")


def stage_visitor_photo(
    db: Session,
    ctx: AuthContext,
    file_stream: BytesIO,
    file_name: str,
    mime_type: str | None,
    size_bytes: int,
    full_name: Optional[str] = None,
    source: str = "UPLOAD",
    location_id: Optional[int] = None,
) -> Dict[str, Any]:
    _require_upload(ctx)
    if location_id and not can_access_location(ctx, location_id):
        raise VisitorMediaError("forbidden", "You do not have access to this location.", 403)

    raw = file_stream.read()
    ext, stored_mime = _validate_image(file_name, mime_type, len(raw), raw)
    _scan_bytes(raw)

    now = datetime.now(timezone.utc)
    rel_dir = ensure_photo_dir(now.year, now.month)
    staged_name = build_staged_filename(full_name, ext.lstrip("."))
    try:
        rel_path = write_bytes(rel_dir, staged_name, raw)
    except LocalMediaStorageError as exc:
        raise VisitorMediaError(exc.code, exc.message, 500)

    row = VisitorMedia(
        media_type=_MEDIA_TYPE_PHOTO,
        status="STAGED",
        storage_rel_path=rel_path,
        stored_filename=staged_name,
        original_filename=(file_name or staged_name)[:255],
        mime_type=stored_mime,
        file_size=len(raw),
        source=source.upper() if source else "UPLOAD",
        created_by_user_id=ctx.user_id,
        location_id=location_id,
        retention_category="VISITOR_PII",
    )
    db.add(row)
    db.flush()
    db.commit()

    return {
        "media_id": row.id,
        "status": row.status,
        "stored_filename": row.stored_filename,
        "mime_type": row.mime_type,
        "file_size": row.file_size,
        "source": row.source,
    }


def delete_staged_photo(db: Session, ctx: AuthContext, media_id: int) -> None:
    _require_upload(ctx)
    row = db.query(VisitorMedia).filter(VisitorMedia.id == media_id).first()
    if not row:
        raise VisitorMediaError("not_found", "Photo not found.", 404)
    if row.created_by_user_id != ctx.user_id and not role_has_permission(ctx.role, Permission.INVITATION_CREATE):
        raise VisitorMediaError("forbidden", "Permission denied.", 403)
    if row.status == "FINALIZED":
        raise VisitorMediaError("immutable", "Registered photo cannot be removed this way.", 400)
    delete_file(row.storage_rel_path)
    row.status = "DELETED"
    db.commit()


def finalize_visitor_photo(
    db: Session,
    media_id: int,
    visitor_id: int,
    visit_id: int,
    location_id: int,
    registration_reference: str,
    full_name: str,
) -> Optional[Dict[str, Any]]:
    row = (
        db.query(VisitorMedia)
        .filter(
            VisitorMedia.id == media_id,
            VisitorMedia.media_type == _MEDIA_TYPE_PHOTO,
            VisitorMedia.status == "STAGED",
        )
        .first()
    )
    if not row:
        return None

    now = datetime.now(timezone.utc)
    rel_dir = ensure_photo_dir(now.year, now.month)
    suffix = registration_reference.replace("/", "_").replace("\\", "_")
    ext = "jpg"
    if "." in row.stored_filename:
        ext = row.stored_filename.rsplit(".", 1)[-1].lower()
    final_name = build_final_filename(full_name, suffix, ext)
    new_rel = f"{rel_dir}/{final_name}"

    try:
        new_rel = rename_file(row.storage_rel_path, new_rel)
    except LocalMediaStorageError:
        raw = read_bytes(row.storage_rel_path)
        new_rel = write_bytes(rel_dir, final_name, raw)
        delete_file(row.storage_rel_path)

    row.storage_rel_path = new_rel
    row.stored_filename = final_name
    row.visitor_id = visitor_id
    row.visit_id = visit_id
    row.location_id = location_id
    row.status = "FINALIZED"
    row.updated_at = now
    db.flush()

    return {
        "media_id": row.id,
        "stored_filename": final_name,
        "display_filename": f"{sanitize_name_prefix(full_name)}.jpg",
        "status": "FINALIZED",
    }


def get_photo_for_view(db: Session, ctx: AuthContext, media_id: int) -> Tuple[bytes, str]:
    _require_read(ctx)
    row = db.query(VisitorMedia).filter(
        VisitorMedia.id == media_id,
        VisitorMedia.media_type == _MEDIA_TYPE_PHOTO,
        VisitorMedia.status == "FINALIZED",
    ).first()
    if not row:
        raise VisitorMediaError("not_found", "Photo not found.", 404)
    if row.location_id and not can_access_location(ctx, row.location_id):
        raise VisitorMediaError("forbidden", "You do not have access to this media.", 403)
    try:
        data = read_bytes(row.storage_rel_path)
    except LocalMediaStorageError as exc:
        raise VisitorMediaError(exc.code, exc.message, 404)
    return data, row.mime_type
