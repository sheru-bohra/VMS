"""Safe filename helpers for visitor media."""

from __future__ import annotations

import re
import secrets
from typing import Optional

_UNSAFE_PATH_RE = re.compile(r"[/\\]+|\.\.+")
_SPACE_RE = re.compile(r"\s+")
_CHARS_RE = re.compile(r"[^\w\-]+", re.UNICODE)
_REPEAT_UNDERSCORE = re.compile(r"_+")


def sanitize_name_prefix(full_name: str, max_len: int = 80) -> str:
    if not full_name or not full_name.strip():
        return "visitor_photo"
    name = full_name.strip()
    name = _UNSAFE_PATH_RE.sub("_", name)
    name = _SPACE_RE.sub("_", name)
    name = _CHARS_RE.sub("_", name)
    name = _REPEAT_UNDERSCORE.sub("_", name).strip("_")
    if not name:
        return "visitor_photo"
    return name[:max_len]


def build_staged_filename(full_name: Optional[str], ext: str = "jpg") -> str:
    token = secrets.token_hex(4)
    prefix = sanitize_name_prefix(full_name or "")
    if prefix == "visitor_photo":
        return f"visitor_photo_{token}.{ext}"
    return f"{prefix}_{token}.{ext}"


def build_final_filename(full_name: str, unique_suffix: str, ext: str = "jpg") -> str:
    safe_suffix = _UNSAFE_PATH_RE.sub("_", unique_suffix.strip())
    safe_suffix = _CHARS_RE.sub("_", safe_suffix).strip("_")[:80]
    prefix = sanitize_name_prefix(full_name)
    return f"{prefix}_{safe_suffix}.{ext}"
