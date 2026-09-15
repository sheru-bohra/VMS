"""Sanitize external provider errors before logging or API exposure."""

from __future__ import annotations

import re
from typing import Optional

_SECRET_PATTERNS = [
    re.compile(r"token\s*=\s*[^\s,]+", re.I),
    re.compile(r"password\s*=\s*[^\s,]+", re.I),
    re.compile(r"access-provider-secret[^\s]*", re.I),
    re.compile(r"printer-secret[^\s]*", re.I),
    re.compile(r"physical-credential-secret[^\s]*", re.I),
    re.compile(r"provider-token[^\s]*", re.I),
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]+", re.I),
]

_AUTH_PATTERNS = [
    re.compile(r"401", re.I),
    re.compile(r"unauthorized", re.I),
    re.compile(r"forbidden", re.I),
    re.compile(r"auth", re.I),
]

_TIMEOUT_PATTERNS = [
    re.compile(r"timeout", re.I),
    re.compile(r"timed out", re.I),
]

_UNAVAILABLE_PATTERNS = [
    re.compile(r"unavailable", re.I),
    re.compile(r"offline", re.I),
    re.compile(r"connection", re.I),
]


def redact_sensitive_text(text: str) -> str:
    out = text
    for pattern in _SECRET_PATTERNS:
        out = pattern.sub("[REDACTED]", out)
    return out


def sanitize_access_provider_error(raw: Optional[str]) -> str:
    if not raw:
        return "ACCESS_PROVIDER_ERROR"
    text = raw.strip()
    for pattern in _SECRET_PATTERNS:
        if pattern.search(text):
            return "ACCESS_PROVIDER_AUTH_FAILED"
    if any(p.search(text) for p in _AUTH_PATTERNS):
        return "ACCESS_PROVIDER_AUTH_FAILED"
    if any(p.search(text) for p in _TIMEOUT_PATTERNS):
        return "ACCESS_PROVIDER_TIMEOUT"
    if any(p.search(text) for p in _UNAVAILABLE_PATTERNS):
        return "ACCESS_PROVIDER_UNAVAILABLE"
    if "invalid" in text.lower() and "profile" in text.lower():
        return "ACCESS_PROVIDER_INVALID_PROFILE"
    return "ACCESS_PROVIDER_ERROR"


def sanitize_badge_printer_error(raw: Optional[str]) -> str:
    if not raw:
        return "BADGE_PRINTER_ERROR"
    text = raw.strip()
    for pattern in _SECRET_PATTERNS:
        if pattern.search(text):
            return "BADGE_PRINTER_AUTH_FAILED"
    if any(p.search(text) for p in _AUTH_PATTERNS):
        return "BADGE_PRINTER_AUTH_FAILED"
    if any(p.search(text) for p in _TIMEOUT_PATTERNS):
        return "BADGE_PRINTER_TIMEOUT"
    if any(p.search(text) for p in _UNAVAILABLE_PATTERNS):
        return "BADGE_PRINTER_UNAVAILABLE"
    return "BADGE_PRINTER_ERROR"
