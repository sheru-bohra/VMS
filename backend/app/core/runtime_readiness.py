"""Cached runtime readiness state for health and operations endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

_audit_cache: Dict[str, Any] = {
    "status": "UNCONFIGURED",
    "verified_at": None,
    "sealed_count": 0,
}


def update_audit_cache(result: Dict[str, Any]) -> None:
    _audit_cache["status"] = result.get("status", "UNCONFIGURED")
    _audit_cache["sealed_count"] = result.get("sealed_count", 0)
    _audit_cache["verified_at"] = datetime.now(timezone.utc).isoformat()


def get_audit_cache() -> Dict[str, Any]:
    return dict(_audit_cache)


_schema_cache: Dict[str, Any] = {
    "current_revision": None,
    "head_revision": None,
    "schema_current": False,
    "checked_at": None,
}


def update_schema_cache(info: Dict[str, Any], schema_current: bool) -> None:
    _schema_cache["current_revision"] = info.get("current_revision") or info.get("current")
    _schema_cache["head_revision"] = info.get("head")
    _schema_cache["schema_current"] = schema_current
    _schema_cache["checked_at"] = datetime.now(timezone.utc).isoformat()


def get_schema_cache() -> Dict[str, Any]:
    return dict(_schema_cache)
