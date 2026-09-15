"""Sanitize sensitive data from logs and configure structured logging."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings
from app.core.runtime_instance import get_runtime_instance_id

_PATTERNS = [
    (re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]+", re.I), "Bearer [REDACTED]"),
    (re.compile(r"Authorization:\s*[^\s,]+", re.I), "Authorization: [REDACTED]"),
    (re.compile(r"(client_secret|graph_client_secret|password|database_url)\s*[=:]\s*[^\s&]+", re.I), r"\1=[REDACTED]"),
    (re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"), "[REDACTED_JWT]"),
    (re.compile(r"gAAAA[A-Za-z0-9_-]+"), "[REDACTED_FERNET]"),
    (re.compile(r"access-provider-secret[^\s]*", re.I), "[REDACTED]"),
    (re.compile(r"printer-secret[^\s]*", re.I), "[REDACTED]"),
    (re.compile(r"physical-credential-secret[^\s]*", re.I), "[REDACTED]"),
    (re.compile(r"provider-token[^\s]*", re.I), "[REDACTED]"),
    (re.compile(r"/host-approval/[A-Za-z0-9_-]+", re.I), "/host-approval/[REDACTED]"),
    (re.compile(r"/invitation/[A-Za-z0-9_-]+", re.I), "/invitation/[REDACTED]"),
    (re.compile(r"postgresql://[^\s]+", re.I), "postgresql://[REDACTED]"),
    (re.compile(r"sqlite://[^\s]+", re.I), "sqlite://[REDACTED]"),
]


def _sanitize(value: str) -> str:
    for pattern, repl in _PATTERNS:
        value = pattern.sub(repl, value)
    return value


class SensitiveLoggingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
            record.msg = _sanitize(msg)
            record.args = ()
        except Exception:
            pass
        return True


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "service": "vms-api",
            "runtime_instance_id": get_runtime_instance_id(),
            "message": _sanitize(record.getMessage()),
            "logger": record.name,
        }
        for key in ("request_id", "method", "route", "status_code", "duration_ms", "error_code", "actor_id", "location_id"):
            if hasattr(record, key) and getattr(record, key) is not None:
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exception"] = _sanitize(self.formatException(record.exc_info))
        return json.dumps(payload, default=str)


def configure_logging() -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)

    handler = logging.StreamHandler()
    if settings.log_format.lower() == "json":
        handler.setFormatter(JsonLogFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s %(message)s"))

    filt = SensitiveLoggingFilter()
    handler.addFilter(filt)
    root.addHandler(handler)
    root.addFilter(filt)
