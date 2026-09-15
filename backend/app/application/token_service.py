"""Generate secure non-sequential tokens."""

import hashlib
import secrets


def generate_public_token(length: int = 32) -> str:
    return secrets.token_urlsafe(length)[:length]


def generate_invitation_token() -> str:
    return secrets.token_urlsafe(48)[:48]


def generate_host_approval_token() -> str:
    return secrets.token_urlsafe(48)[:48]


def hash_host_approval_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
