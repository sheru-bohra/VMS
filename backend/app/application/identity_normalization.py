"""Identity normalization for security screening."""

from __future__ import annotations

import re
import unicodedata

_PHONE_RE = re.compile(r"[^\d+]")
_NAME_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_SPACE_RE = re.compile(r"\s+")


def normalize_mobile(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = _PHONE_RE.sub("", value.strip())
    return cleaned or None


def normalize_email(value: str | None) -> str | None:
    if not value:
        return None
    return value.strip().lower() or None


def normalize_company(value: str | None) -> str | None:
    if not value:
        return None
    text = value.strip().casefold()
    text = _SPACE_RE.sub(" ", text)
    return text or None


def normalize_person_name(value: str | None) -> str | None:
    if not value:
        return None
    text = unicodedata.normalize("NFKC", value.strip()).casefold()
    text = _NAME_PUNCT_RE.sub(" ", text)
    text = _SPACE_RE.sub(" ", text).strip()
    return text or None


def name_similarity(a: str | None, b: str | None) -> int:
    if not a or not b:
        return 0
    from rapidfuzz import fuzz

    return int(fuzz.ratio(a, b))
