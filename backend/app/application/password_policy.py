"""Enterprise password policy for VMS native authentication."""

from __future__ import annotations

import secrets
import string

from app.core.errors import APIError

_MIN_LENGTH = 12
_WEAK_PASSWORDS = frozenset(
    {
        "password",
        "password1234",
        "changeme",
        "123456789012",
        "qwertyuiop12",
        "welcome12345",
    }
)


def password_meets_policy(password: str) -> bool:
    try:
        validate_password_policy(password)
        return True
    except APIError:
        return False


def validate_password_policy(password: str) -> None:
    if not password or len(password) < _MIN_LENGTH:
        raise APIError(
            400,
            "validation_error",
            f"Password must be at least {_MIN_LENGTH} characters.",
        )
    if password.strip() != password:
        raise APIError(400, "validation_error", "Password must not have leading or trailing spaces.")
    if password.lower() in _WEAK_PASSWORDS:
        raise APIError(400, "validation_error", "Password is too weak. Choose a stronger password.")


def validate_password_confirmation(password: str, confirmation: str) -> None:
    if password != confirmation:
        raise APIError(400, "validation_error", "Password confirmation does not match.")


def generate_temporary_password(length: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%&*"
    while True:
        candidate = "".join(secrets.choice(alphabet) for _ in range(length))
        try:
            validate_password_policy(candidate)
            return candidate
        except APIError:
            continue
