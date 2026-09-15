"""Phase 11: AI intelligence and copilot

Revision ID: 010
Revises: 009
Create Date: 2026-08-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(bind, name: str) -> bool:
    return name in inspect(bind).get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, "ai_insights"):
        op.create_table(
            "ai_insights",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("insight_type", sa.String(length=50), nullable=False),
            sa.Column("location_id", sa.Integer(), nullable=True),
            sa.Column("visit_id", sa.Integer(), nullable=True),
            sa.Column("visitor_id", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="ACTIVE"),
            sa.Column("priority", sa.String(length=20), nullable=False, server_default="INFORMATION"),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("summary", sa.Text(), nullable=False),
            sa.Column("evidence_json", sa.Text(), nullable=True),
            sa.Column("fingerprint", sa.String(length=128), nullable=False),
            sa.Column("rules_version", sa.String(length=20), nullable=False, server_default="v1"),
            sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("dismissed_by_user_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
            sa.ForeignKeyConstraint(["dismissed_by_user_id"], ["admin_users.id"]),
            sa.ForeignKeyConstraint(["location_id"], ["locations.id"]),
            sa.ForeignKeyConstraint(["visit_id"], ["visits.id"]),
            sa.ForeignKeyConstraint(["visitor_id"], ["visitors.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("fingerprint"),
        )
        op.create_index(op.f("ix_ai_insights_insight_type"), "ai_insights", ["insight_type"], unique=False)
        op.create_index(op.f("ix_ai_insights_location_id"), "ai_insights", ["location_id"], unique=False)
        op.create_index(op.f("ix_ai_insights_status"), "ai_insights", ["status"], unique=False)
        op.create_index(op.f("ix_ai_insights_priority"), "ai_insights", ["priority"], unique=False)
        op.create_index(op.f("ix_ai_insights_visit_id"), "ai_insights", ["visit_id"], unique=False)
        op.create_index(op.f("ix_ai_insights_generated_at"), "ai_insights", ["generated_at"], unique=False)
        op.create_index(op.f("ix_ai_insights_fingerprint"), "ai_insights", ["fingerprint"], unique=True)

    if not _table_exists(bind, "ai_sessions"):
        op.create_table(
            "ai_sessions",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["admin_users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_ai_sessions_user_id"), "ai_sessions", ["user_id"], unique=False)

    if not _table_exists(bind, "ai_interactions"):
        op.create_table(
            "ai_interactions",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("session_id", sa.Integer(), nullable=True),
            sa.Column("intent", sa.String(length=50), nullable=False),
            sa.Column("location_scope_json", sa.Text(), nullable=True),
            sa.Column("question_redacted", sa.Text(), nullable=True),
            sa.Column("response_summary", sa.Text(), nullable=True),
            sa.Column("provider", sa.String(length=50), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="COMPLETED"),
            sa.Column("duration_ms", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
            sa.ForeignKeyConstraint(["session_id"], ["ai_sessions.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["admin_users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_ai_interactions_user_id"), "ai_interactions", ["user_id"], unique=False)
        op.create_index(op.f("ix_ai_interactions_session_id"), "ai_interactions", ["session_id"], unique=False)
        op.create_index(op.f("ix_ai_interactions_created_at"), "ai_interactions", ["created_at"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    if _table_exists(bind, "ai_interactions"):
        op.drop_table("ai_interactions")
    if _table_exists(bind, "ai_sessions"):
        op.drop_table("ai_sessions")
    if _table_exists(bind, "ai_insights"):
        op.drop_table("ai_insights")
