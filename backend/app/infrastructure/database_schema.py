"""Alembic schema revision checks."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent


class SchemaMismatchError(RuntimeError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def _alembic_config() -> Config:
    ini_path = BACKEND_ROOT / "alembic.ini"
    cfg = Config(str(ini_path))
    return cfg


def get_head_revision() -> str:
    script = ScriptDirectory.from_config(_alembic_config())
    head = script.get_current_head()
    if not head:
        raise SchemaMismatchError("DATABASE_SCHEMA_UNKNOWN", "Alembic head revision not found.")
    return head


def get_database_revision(connection: Connection) -> Optional[str]:
    context = MigrationContext.configure(connection)
    return context.get_current_revision()


def get_revision_display_name(revision: str) -> str:
    versions_dir = BACKEND_ROOT / "alembic" / "versions"
    for path in versions_dir.glob(f"{revision}_*.py"):
        return path.stem
    return revision


def check_schema_at_head(engine: Engine, require_version: bool = False) -> dict:
    head = get_head_revision()
    with engine.connect() as connection:
        current = get_database_revision(connection)
        connection.execute(text("SELECT 1"))
    if current is None:
        if require_version:
            raise SchemaMismatchError(
                "DATABASE_SCHEMA_OUTDATED",
                "Database has no Alembic revision. Run migrations before starting the application.",
            )
        return {
            "current": None,
            "head": head,
            "current_revision": None,
            "schema_current": False,
        }
    if current != head:
        if _revision_rank(current) > _revision_rank(head):
            raise SchemaMismatchError(
                "DATABASE_SCHEMA_AHEAD",
                f"Database revision {current} is ahead of application head {head}.",
            )
        if require_version:
            raise SchemaMismatchError(
                "DATABASE_SCHEMA_OUTDATED",
                f"Database revision {current} is behind application head {head}.",
            )
        return {
            "current": current,
            "head": head,
            "current_revision": current,
            "revision_display": get_revision_display_name(current),
            "schema_current": False,
        }
    return {
        "current": current,
        "head": head,
        "current_revision": current,
        "revision_display": get_revision_display_name(current),
        "schema_current": True,
    }


def _revision_rank(revision: str) -> int:
    try:
        return int(revision)
    except ValueError:
        return 0
