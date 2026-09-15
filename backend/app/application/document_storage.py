"""Local encrypted document storage with quarantine scanning."""

from __future__ import annotations

import os
import re
import secrets
import tempfile
from pathlib import Path
from typing import BinaryIO, Tuple

from app.application.document_encryption import decrypt_bytes, encrypt_bytes, DocumentEncryptionError
from app.application.file_security_scanner import get_file_security_scanner, ScanResult
from app.core.config import settings

_ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
_ALLOWED_MIME = {
    "application/pdf",
    "image/jpeg",
    "image/jpg",
    "image/png",
}
_UNSAFE_NAME_RE = re.compile(r"[^\w.\-]+", re.UNICODE)


class DocumentStorageError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def _sanitize_display_name(name: str) -> str:
    base = os.path.basename(name or "document")
    base = _UNSAFE_NAME_RE.sub("_", base.strip())
    return base[:200] or "document"


def validate_upload(file_name: str, mime_type: str | None, size_bytes: int) -> None:
    max_bytes = settings.compliance_document_max_mb * 1024 * 1024
    if size_bytes <= 0:
        raise DocumentStorageError("empty_file", "Uploaded file is empty.")
    if size_bytes > max_bytes:
        raise DocumentStorageError("file_too_large", f"File exceeds {settings.compliance_document_max_mb} MB limit.")
    raw_name = file_name or ""
    if ".." in raw_name or "/" in raw_name or "\\" in raw_name:
        raise DocumentStorageError("invalid_file_name", "Invalid file name.")
    ext = Path(file_name or "").suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise DocumentStorageError("invalid_file_type", "Only PDF, JPG, JPEG, and PNG files are allowed.")
    if mime_type and mime_type.lower() not in _ALLOWED_MIME:
        raise DocumentStorageError("invalid_mime", "Unsupported file type.")


def generate_storage_key(extension: str) -> str:
    ext = extension.lower() if extension else ""
    if ext and not ext.startswith("."):
        ext = f".{ext}"
    if ext not in _ALLOWED_EXTENSIONS:
        ext = ".bin"
    token = secrets.token_hex(24)
    return f"{token}{ext}.enc"


class EncryptedDocumentStorageProvider:
    def __init__(self, root: Path | None = None, quarantine_root: Path | None = None):
        self.root = root or settings.compliance_upload_root
        self.quarantine_root = quarantine_root or (settings.compliance_upload_root.parent / "quarantine")
        self.quarantine_root.mkdir(parents=True, exist_ok=True)
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, file_stream: BinaryIO, file_name: str, mime_type: str | None, size_bytes: int) -> Tuple[str, str, str, bool, int | None]:
        validate_upload(file_name, mime_type, size_bytes)
        display_name = _sanitize_display_name(file_name)
        ext = Path(display_name).suffix.lower()
        scanner = get_file_security_scanner()

        fd, quarantine_path = tempfile.mkstemp(prefix="vq_", dir=str(self.quarantine_root))
        os.close(fd)
        try:
            with open(quarantine_path, "wb") as out:
                while True:
                    chunk = file_stream.read(65536)
                    if not chunk:
                        break
                    out.write(chunk)

            scan_result = scanner.scan_file(quarantine_path)
            if settings.is_production and scan_result == ScanResult.SCANNER_UNAVAILABLE:
                raise DocumentStorageError("FILE_SCANNER_UNAVAILABLE", "File security scanner is unavailable.")
            if scan_result == ScanResult.INFECTED:
                raise DocumentStorageError("FILE_SECURITY_REJECTED", "File was rejected by security scanning.")

            with open(quarantine_path, "rb") as fh:
                plaintext = fh.read()

            encrypted = False
            enc_version: int | None = None
            storage_key = generate_storage_key(ext)
            dest = self.root / storage_key

            try:
                blob, enc_version = encrypt_bytes(plaintext)
                encrypted = True
                with open(dest, "wb") as out:
                    out.write(blob)
            except DocumentEncryptionError:
                if settings.is_production:
                    raise DocumentStorageError("encryption_unavailable", "Document encryption is not configured.")
                storage_key = storage_key.replace(".enc", ext if ext else ".bin")
                dest = self.root / storage_key
                with open(dest, "wb") as out:
                    out.write(plaintext)

            return storage_key, display_name, scan_result, encrypted, enc_version
        finally:
            try:
                os.unlink(quarantine_path)
            except OSError:
                pass

    def read_decrypted(self, storage_key: str, encrypted: bool, encryption_version: int | None) -> bytes:
        if not storage_key or ".." in storage_key or storage_key.startswith("/"):
            raise DocumentStorageError("invalid_key", "Invalid storage key.")
        path = (self.root / storage_key).resolve()
        if not str(path).startswith(str(self.root.resolve())):
            raise DocumentStorageError("invalid_key", "Invalid storage key.")
        if not path.is_file():
            raise DocumentStorageError("not_found", "Document file not found.")
        data = path.read_bytes()
        if encrypted:
            return decrypt_bytes(data, encryption_version)
        return data

    def delete_file(self, storage_key: str) -> bool:
        if not storage_key or ".." in storage_key:
            return False
        path = (self.root / storage_key).resolve()
        if not str(path).startswith(str(self.root.resolve())):
            return False
        if path.is_file():
            path.unlink()
            return True
        return False

    def resolve_path(self, storage_key: str) -> Path:
        """Legacy path resolution for unencrypted files in development."""
        if not storage_key or ".." in storage_key or storage_key.startswith("/"):
            raise DocumentStorageError("invalid_key", "Invalid storage key.")
        path = (self.root / storage_key).resolve()
        if not str(path).startswith(str(self.root.resolve())):
            raise DocumentStorageError("invalid_key", "Invalid storage key.")
        if not path.is_file():
            raise DocumentStorageError("not_found", "Document file not found.")
        return path


document_storage = EncryptedDocumentStorageProvider()


def purge_stale_quarantine(max_age_seconds: int = 3600) -> int:
    root = document_storage.quarantine_root
    if not root.exists():
        return 0
    import time

    now = time.time()
    removed = 0
    for entry in root.iterdir():
        if entry.is_file() and now - entry.stat().st_mtime > max_age_seconds:
            try:
                entry.unlink()
                removed += 1
            except OSError:
                pass
    return removed
