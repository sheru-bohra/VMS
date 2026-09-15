"""Centralized SQLAlchemy engine configuration for SQLite and PostgreSQL."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine

from app.core.config import settings

logger = logging.getLogger(__name__)


def _dialect_from_url(url: str) -> str:
    if url.startswith("postgresql"):
        return "postgresql"
    if url.startswith("sqlite"):
        return "sqlite"
    return "unknown"


def build_engine(url: Optional[str] = None) -> Tuple[Engine, str]:
    db_url = url or settings.resolved_database_url()
    dialect = _dialect_from_url(db_url)
    connect_args: Dict[str, Any] = {}
    engine_kwargs: Dict[str, Any] = {
        "pool_pre_ping": False,
        "echo": settings.db_sql_echo and not settings.is_production,
    }

    if dialect == "sqlite":
        connect_args["check_same_thread"] = False
    elif dialect == "postgresql":
        engine_kwargs["pool_pre_ping"] = True
        engine_kwargs["pool_size"] = settings.db_pool_size
        engine_kwargs["max_overflow"] = settings.db_max_overflow
        engine_kwargs["pool_timeout"] = settings.db_pool_timeout_seconds
        engine_kwargs["pool_recycle"] = settings.db_pool_recycle_seconds
        connect_args["connect_timeout"] = settings.db_connect_timeout_seconds
        if settings.db_sslmode:
            connect_args["sslmode"] = settings.db_sslmode
        if settings.db_application_name:
            connect_args["application_name"] = settings.db_application_name

    engine = create_engine(db_url, connect_args=connect_args, **engine_kwargs)

    if dialect == "postgresql" and settings.db_statement_timeout_ms > 0:
        timeout_ms = settings.db_statement_timeout_ms

        @event.listens_for(engine, "connect")
        def _set_statement_timeout(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute(f"SET statement_timeout = {timeout_ms}")
            cursor.close()

    logger.info(
        "Database engine configured dialect=%s pool_pre_ping=%s",
        dialect,
        engine_kwargs.get("pool_pre_ping", False),
    )
    return engine, dialect


def validate_production_database_policy(url: str) -> None:
    if not settings.is_production:
        return
    dialect = _dialect_from_url(url)
    required = settings.production_database_dialect.lower()
    if required == "postgresql" and dialect != "postgresql":
        raise RuntimeError(
            "Production requires PostgreSQL DATABASE_URL. SQLite is not permitted when APP_ENV=production."
        )
