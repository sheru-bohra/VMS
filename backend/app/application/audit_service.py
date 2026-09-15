from __future__ import annotations

from typing import Any, Dict, Optional

import json
from sqlalchemy.orm import Session

from app.domain.models import AuditEvent
from app.application.audit_integrity_service import seal_event


class AuditService:
    def __init__(self, db: Session):
        self._db = db

    def record(
        self,
        action: str,
        entity_type: str,
        entity_id: Optional[str] = None,
        actor_id: Optional[int] = None,
        actor_email: Optional[str] = None,
        location_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        before_value: Any = None,
        after_value: Any = None,
    ) -> AuditEvent:
        event = AuditEvent(
            actor_id=actor_id,
            actor_email=actor_email,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            location_id=location_id,
            metadata_json=json.dumps(metadata) if metadata else None,
            before_value=json.dumps(before_value) if before_value is not None else None,
            after_value=json.dumps(after_value) if after_value is not None else None,
        )
        self._db.add(event)
        self._db.flush()
        try:
            seal_event(self._db, event)
        except Exception:
            # Integrity sealing optional in dev without key
            pass
        return event
