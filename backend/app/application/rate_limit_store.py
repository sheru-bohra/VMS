"""Rate limit storage backends."""

from __future__ import annotations

import hashlib
import threading
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Dict, List

from sqlalchemy.orm import Session

from app.domain.models import RateLimitBucket


class RateLimitStore(ABC):
    @abstractmethod
    def check_and_increment(self, key: str, limit: int, window_seconds: int = 60) -> bool:
        """Return True if allowed, False if rate limited."""


def hash_rate_limit_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


class InMemoryRateLimitStore(RateLimitStore):
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._hits: Dict[str, List[float]] = {}

    def check_and_increment(self, key: str, limit: int, window_seconds: int = 60) -> bool:
        hashed = hash_rate_limit_key(key)
        now = time.time()
        cutoff = now - window_seconds
        with self._lock:
            hits = self._hits.get(hashed, [])
            hits = [t for t in hits if t > cutoff]
            if len(hits) >= limit:
                return False
            hits.append(now)
            self._hits[hashed] = hits
            return True


class DatabaseRateLimitStore(RateLimitStore):
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def check_and_increment(self, key: str, limit: int, window_seconds: int = 60) -> bool:
        hashed = hash_rate_limit_key(key)
        now = datetime.now(timezone.utc)
        window_start = now.replace(second=0, microsecond=0)
        if window_seconds >= 60:
            window_start = window_start.replace(minute=window_start.minute)
        expires_at = window_start + timedelta(seconds=window_seconds + 60)

        db: Session = self._session_factory()
        try:
            row = (
                db.query(RateLimitBucket)
                .filter(
                    RateLimitBucket.key_hash == hashed,
                    RateLimitBucket.window_start == window_start,
                )
                .first()
            )
            if not row:
                row = RateLimitBucket(
                    key_hash=hashed,
                    window_start=window_start,
                    count=1,
                    expires_at=expires_at,
                )
                db.add(row)
                db.commit()
                return True
            if row.count >= limit:
                db.commit()
                return False
            row.count += 1
            db.commit()
            return True
        finally:
            db.close()


_memory_store = InMemoryRateLimitStore()
_db_store: DatabaseRateLimitStore | None = None


def get_rate_limit_store(session_factory=None) -> RateLimitStore:
    from app.core.config import settings

    if settings.rate_limit_backend == "database" and session_factory:
        global _db_store
        if _db_store is None:
            _db_store = DatabaseRateLimitStore(session_factory)
        return _db_store
    return _memory_store
