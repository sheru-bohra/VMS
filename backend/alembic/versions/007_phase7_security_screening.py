"""Phase 7: security screening and watchlist

Revision ID: 007
Revises: 006
Create Date: 2026-08-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(bind, name: str) -> bool:
    return name in inspect(bind).get_table_names()


def _visit_columns(bind) -> set[str]:
    return {c["name"] for c in inspect(bind).get_columns("visits")}


def upgrade() -> None:
    bind = op.get_bind()
    visit_cols = _visit_columns(bind)
    if "security_clearance_status" not in visit_cols:
        op.add_column(
            "visits",
            sa.Column("security_clearance_status", sa.String(length=20), nullable=False, server_default="CLEAR"),
        )
        op.create_index(op.f("ix_visits_security_clearance_status"), "visits", ["security_clearance_status"], unique=False)

    if not _table_exists(bind, "watchlist_entries"):
        op.create_table(
            "watchlist_entries",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("scope_type", sa.String(length=20), nullable=False),
            sa.Column("location_id", sa.Integer(), nullable=True),
            sa.Column("full_name", sa.String(length=255), nullable=False),
            sa.Column("normalized_name", sa.String(length=255), nullable=False),
            sa.Column("mobile", sa.String(length=50), nullable=True),
            sa.Column("normalized_mobile", sa.String(length=50), nullable=True),
            sa.Column("email", sa.String(length=255), nullable=True),
            sa.Column("normalized_email", sa.String(length=255), nullable=True),
            sa.Column("company", sa.String(length=255), nullable=True),
            sa.Column("normalized_company", sa.String(length=255), nullable=True),
            sa.Column("reason_code", sa.String(length=50), nullable=False),
            sa.Column("reason_text", sa.Text(), nullable=True),
            sa.Column("action_level", sa.String(length=20), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="ACTIVE"),
            sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
            sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_by_user_id", sa.Integer(), nullable=True),
            sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
            sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["admin_users.id"]),
            sa.ForeignKeyConstraint(["location_id"], ["locations.id"]),
            sa.ForeignKeyConstraint(["updated_by_user_id"], ["admin_users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_watchlist_entries_scope_type"), "watchlist_entries", ["scope_type"], unique=False)
        op.create_index(op.f("ix_watchlist_entries_location_id"), "watchlist_entries", ["location_id"], unique=False)
        op.create_index(op.f("ix_watchlist_entries_normalized_name"), "watchlist_entries", ["normalized_name"], unique=False)
        op.create_index(op.f("ix_watchlist_entries_normalized_mobile"), "watchlist_entries", ["normalized_mobile"], unique=False)
        op.create_index(op.f("ix_watchlist_entries_normalized_email"), "watchlist_entries", ["normalized_email"], unique=False)
        op.create_index(op.f("ix_watchlist_entries_status"), "watchlist_entries", ["status"], unique=False)

    if not _table_exists(bind, "security_screenings"):
        op.create_table(
            "security_screenings",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("visit_id", sa.Integer(), nullable=False),
            sa.Column("visitor_id", sa.Integer(), nullable=False),
            sa.Column("location_id", sa.Integer(), nullable=False),
            sa.Column("outcome", sa.String(length=20), nullable=False),
            sa.Column("screened_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
            sa.Column("screening_version", sa.String(length=20), nullable=False, server_default="v1"),
            sa.Column("watchlist_match_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("highest_match_confidence", sa.String(length=20), nullable=True),
            sa.Column("matched_watchlist_entry_id", sa.Integer(), nullable=True),
            sa.Column("duplicate_signal_level", sa.String(length=30), nullable=True),
            sa.Column("reason_summary", sa.Text(), nullable=True),
            sa.Column("signals_json", sa.Text(), nullable=True),
            sa.Column("trigger", sa.String(length=50), nullable=True),
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("resolved_by_user_id", sa.Integer(), nullable=True),
            sa.Column("resolution", sa.String(length=30), nullable=True),
            sa.Column("resolution_comment", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(["location_id"], ["locations.id"]),
            sa.ForeignKeyConstraint(["matched_watchlist_entry_id"], ["watchlist_entries.id"]),
            sa.ForeignKeyConstraint(["resolved_by_user_id"], ["admin_users.id"]),
            sa.ForeignKeyConstraint(["visit_id"], ["visits.id"]),
            sa.ForeignKeyConstraint(["visitor_id"], ["visitors.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_security_screenings_visit_id"), "security_screenings", ["visit_id"], unique=False)
        op.create_index(op.f("ix_security_screenings_location_id"), "security_screenings", ["location_id"], unique=False)
        op.create_index(op.f("ix_security_screenings_outcome"), "security_screenings", ["outcome"], unique=False)
        op.create_index(op.f("ix_security_screenings_screened_at"), "security_screenings", ["screened_at"], unique=False)

    if not _table_exists(bind, "watchlist_matches"):
        op.create_table(
            "watchlist_matches",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("screening_id", sa.Integer(), nullable=False),
            sa.Column("watchlist_entry_id", sa.Integer(), nullable=False),
            sa.Column("confidence", sa.String(length=20), nullable=False),
            sa.Column("matched_signals", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(["screening_id"], ["security_screenings.id"]),
            sa.ForeignKeyConstraint(["watchlist_entry_id"], ["watchlist_entries.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_watchlist_matches_screening_id"), "watchlist_matches", ["screening_id"], unique=False)
        op.create_index(op.f("ix_watchlist_matches_watchlist_entry_id"), "watchlist_matches", ["watchlist_entry_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    if _table_exists(bind, "watchlist_matches"):
        op.drop_table("watchlist_matches")
    if _table_exists(bind, "security_screenings"):
        op.drop_table("security_screenings")
    if _table_exists(bind, "watchlist_entries"):
        op.drop_table("watchlist_entries")
    visit_cols = _visit_columns(bind)
    if "security_clearance_status" in visit_cols:
        op.drop_index(op.f("ix_visits_security_clearance_status"), table_name="visits")
        op.drop_column("visits", "security_clearance_status")
