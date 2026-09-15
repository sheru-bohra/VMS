"""Process runtime identity for scheduler lease coordination."""

from __future__ import annotations

import uuid

_runtime_instance_id: str = uuid.uuid4().hex


def get_runtime_instance_id() -> str:
    return _runtime_instance_id


def masked_runtime_instance_id() -> str:
    rid = _runtime_instance_id
    return f"inst-{rid[:8]}"
