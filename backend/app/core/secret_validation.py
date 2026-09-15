"""Production secret strength validation."""

from __future__ import annotations

import base64
import re

_WEAK_PATTERNS = re.compile(
    r"(changeme|password|secret|development|test|example|default|placeholder)",
    re.I,
)


def is_weak_secret(value: str | None, min_length: int = 32) -> bool:
    if not value or len(value.strip()) < min_length:
        return True
    if _WEAK_PATTERNS.search(value):
        return True
    return False


def validate_production_secret(name: str, value: str | None, min_length: int = 32) -> None:
    if is_weak_secret(value, min_length):
        raise RuntimeError(f"{name} is missing or does not meet production strength requirements.")
