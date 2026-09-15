"""Phase 15: runtime coordination for multi-instance scheduler safety

Revision ID: 014
Revises: 013
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(bind, name: str) -> bool:
    return name in inspect(bind).get_table_names()


def upgrade() -> None:
    bind = op.get_bind()

    if not _table_exists(bind, "runtime_leases"):
        op.create_table(
            "runtime_leases",
            sa.Column("lease_name", sa.String(64), primary_key=True),
            sa.Column("owner_id", sa.String(64), nullable=False),
            sa.Column("leased_until", sa.DateTime(timezone=True), nullable=False),
            sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_cycle_started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_cycle_completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_error_code", sa.String(100), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_runtime_leases_leased_until", "runtime_leases", ["leased_until"])

    if bind.dialect.name == "postgresql":
        op.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_emergency_active_per_location "
            "ON emergency_events (location_id) WHERE status = 'ACTIVE'"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS uq_emergency_active_per_location")
    if _table_exists(bind, "runtime_leases"):
        op.drop_table("runtime_leases")
