"""PII minimization and secret redaction before AI provider invocation."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

_TOKEN_PATTERNS = [
    re.compile(r"[a-f0-9]{32,64}", re.I),
    re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"),
]
_SENSITIVE_KEYS = frozenset({
    "invitation_token",
    "token",
    "token_hash",
    "password",
    "api_key",
    "jwt",
    "authorization",
    "mobile",
    "phone",
    "email",
    "document_path",
    "storage_path",
    "watchlist_reason",
    "security_comment",
    "matched_identifiers",
})


def _redact_string(value: str) -> str:
    s = value
    for pat in _TOKEN_PATTERNS:
        s = pat.sub("[REDACTED]", s)
    return s


def redact_value(key: str, value: Any, include_contact: bool = False) -> Any:
    if value is None:
        return None
    lk = key.lower()
    if lk in _SENSITIVE_KEYS:
        if include_contact and lk in ("mobile", "phone", "email"):
            return value
        return "[REDACTED]"
    if "token" in lk or "path" in lk:
        return "[REDACTED]"
    if isinstance(value, str):
        return _redact_string(value)
    if isinstance(value, dict):
        return redact_dict(value, include_contact=include_contact)
    if isinstance(value, list):
        return [redact_value(key, item, include_contact=include_contact) for item in value[:100]]
    return value


def redact_dict(data: Dict[str, Any], include_contact: bool = False) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k, v in data.items():
        out[k] = redact_value(k, v, include_contact=include_contact)
    return out


def redact_question(question: str, max_len: int = 1000) -> str:
    q = question.strip()[:max_len]
    return _redact_string(q)


def contains_forbidden_tokens(context: Dict[str, Any]) -> List[str]:
    """Test helper: find obvious token leaks in serialized context."""
    import json
    text = json.dumps(context)
    leaks = []
    if "eyJ" in text and "[REDACTED]" not in text:
        leaks.append("jwt_pattern")
    for pat in _TOKEN_PATTERNS:
        for m in pat.finditer(text):
            if m.group() not in ("[REDACTED]",):
                leaks.append(m.group()[:20])
    return leaks
