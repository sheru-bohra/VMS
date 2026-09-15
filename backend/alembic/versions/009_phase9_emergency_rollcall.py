"""Phase 9: emergency roll-call

Revision ID: 009
Revises: 008
Create Date: 2026-08-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(bind, name: str) -> bool:
    return name in inspect(bind).get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, "emergency_events"):
        op.create_table(
            "emergency_events",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("location_id", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="ACTIVE"),
            sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
            sa.Column("started_by_user_id", sa.Integer(), nullable=False),
            sa.Column("reason", sa.String(length=50), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("visitor_snapshot_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("closed_by_user_id", sa.Integer(), nullable=True),
            sa.Column("closure_comment", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
            sa.ForeignKeyConstraint(["closed_by_user_id"], ["admin_users.id"]),
            sa.ForeignKeyConstraint(["location_id"], ["locations.id"]),
            sa.ForeignKeyConstraint(["started_by_user_id"], ["admin_users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_emergency_events_location_id"), "emergency_events", ["location_id"], unique=False)
        op.create_index(op.f("ix_emergency_events_status"), "emergency_events", ["status"], unique=False)
        op.create_index(op.f("ix_emergency_events_started_at"), "emergency_events", ["started_at"], unique=False)

    if not _table_exists(bind, "emergency_roll_call_entries"):
        op.create_table(
            "emergency_roll_call_entries",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("emergency_event_id", sa.Integer(), nullable=False),
            sa.Column("visit_id", sa.Integer(), nullable=False),
            sa.Column("visitor_id", sa.Integer(), nullable=False),
            sa.Column("snapshot_visitor_name", sa.String(length=255), nullable=False),
            sa.Column("snapshot_company", sa.String(length=255), nullable=True),
            sa.Column("snapshot_visitor_type", sa.String(length=100), nullable=True),
            sa.Column("snapshot_host_name", sa.String(length=255), nullable=True),
            sa.Column("snapshot_mobile", sa.String(length=50), nullable=True),
            sa.Column("snapshot_registration_reference", sa.String(length=50), nullable=True),
            sa.Column("snapshot_badge_number", sa.String(length=50), nullable=True),
            sa.Column("snapshot_checked_in_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="UNACCOUNTED"),
            sa.Column("status_updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("status_updated_by_user_id", sa.Integer(), nullable=True),
            sa.Column("comment", sa.Text(), nullable=True),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("visit_checked_out_after_start", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
            sa.ForeignKeyConstraint(["emergency_event_id"], ["emergency_events.id"]),
            sa.ForeignKeyConstraint(["status_updated_by_user_id"], ["admin_users.id"]),
            sa.ForeignKeyConstraint(["visit_id"], ["visits.id"]),
            sa.ForeignKeyConstraint(["visitor_id"], ["visitors.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_emergency_roll_call_entries_emergency_event_id"), "emergency_roll_call_entries", ["emergency_event_id"], unique=False)
        op.create_index(op.f("ix_emergency_roll_call_entries_visit_id"), "emergency_roll_call_entries", ["visit_id"], unique=False)
        op.create_index(op.f("ix_emergency_roll_call_entries_visitor_id"), "emergency_roll_call_entries", ["visitor_id"], unique=False)
        op.create_index(op.f("ix_emergency_roll_call_entries_status"), "emergency_roll_call_entries", ["status"], unique=False)

    if not _table_exists(bind, "emergency_roll_call_actions"):
        op.create_table(
            "emergency_roll_call_actions",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("emergency_event_id", sa.Integer(), nullable=False),
            sa.Column("roll_call_entry_id", sa.Integer(), nullable=False),
            sa.Column("old_status", sa.String(length=30), nullable=False),
            sa.Column("new_status", sa.String(length=30), nullable=False),
            sa.Column("actor_user_id", sa.Integer(), nullable=False),
            sa.Column("actor_email", sa.String(length=255), nullable=True),
            sa.Column("comment", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
            sa.ForeignKeyConstraint(["actor_user_id"], ["admin_users.id"]),
            sa.ForeignKeyConstraint(["emergency_event_id"], ["emergency_events.id"]),
            sa.ForeignKeyConstraint(["roll_call_entry_id"], ["emergency_roll_call_entries.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_emergency_roll_call_actions_emergency_event_id"), "emergency_roll_call_actions", ["emergency_event_id"], unique=False)
        op.create_index(op.f("ix_emergency_roll_call_actions_roll_call_entry_id"), "emergency_roll_call_actions", ["roll_call_entry_id"], unique=False)
        op.create_index(op.f("ix_emergency_roll_call_actions_created_at"), "emergency_roll_call_actions", ["created_at"], unique=False)

    # Partial unique index: one ACTIVE emergency per location (SQLite supports partial indexes)
    try:
        op.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_emergency_active_per_location "
            "ON emergency_events (location_id) WHERE status = 'ACTIVE'"
        )
    except Exception:
        pass


def downgrade() -> None:
    bind = op.get_bind()
    if _table_exists(bind, "emergency_roll_call_actions"):
        op.drop_table("emergency_roll_call_actions")
    if _table_exists(bind, "emergency_roll_call_entries"):
        op.drop_table("emergency_roll_call_entries")
    if _table_exists(bind, "emergency_events"):
        try:
            op.execute("DROP INDEX IF EXISTS uq_emergency_active_per_location")
        except Exception:
            pass
        op.drop_table("emergency_events")
