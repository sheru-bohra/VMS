"""Authenticated encryption for short-lived delivery secrets."""

from __future__ import annotations

import base64
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


class EncryptionError(Exception):
    pass


def _fernet() -> Optional[Fernet]:
    key = settings.vms_data_encryption_key
    if not key:
        return None
    try:
        return Fernet(key.encode("utf-8") if not key.startswith("gAAAA") else key)
    except Exception:
        # Allow raw Fernet key generation format
        return Fernet(key)


def encrypt_value(plaintext: str) -> str:
    f = _fernet()
    if not f:
        raise EncryptionError("Encryption key not configured.")
    return f.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_value(ciphertext: str) -> str:
    f = _fernet()
    if not f:
        raise EncryptionError("Encryption key not configured.")
    try:
        return f.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        raise EncryptionError("Invalid encrypted value.")


def generate_encryption_key() -> str:
    return Fernet.generate_key().decode("utf-8")
