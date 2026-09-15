"""AES-GCM document encryption at rest."""

from __future__ import annotations

import os
from typing import Tuple

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings
from app.core.secret_validation import is_weak_secret


class DocumentEncryptionError(Exception):
    pass


def _key_bytes() -> bytes:
    key = settings.document_encryption_key
    if not key or is_weak_secret(key, 32):
        raise DocumentEncryptionError("Document encryption key not configured.")
    raw = key.encode("utf-8")
    if len(raw) >= 32:
        return raw[:32]
    return raw + b"\0" * (32 - len(raw))


def encrypt_bytes(plaintext: bytes) -> Tuple[bytes, int]:
    version = settings.document_encryption_version
    nonce = os.urandom(12)
    aesgcm = AESGCM(_key_bytes())
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return nonce + ciphertext, version


def decrypt_bytes(blob: bytes, version: int | None) -> bytes:
    if version != settings.document_encryption_version:
        raise DocumentEncryptionError("Unsupported encryption version.")
    if len(blob) < 13:
        raise DocumentEncryptionError("Invalid encrypted blob.")
    nonce, ciphertext = blob[:12], blob[12:]
    aesgcm = AESGCM(_key_bytes())
    return aesgcm.decrypt(nonce, ciphertext, None)
