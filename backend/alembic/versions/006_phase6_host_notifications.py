"""Phase 6: host approval requests and notifications

Revision ID: 006
Revises: 005
Create Date: 2026-08-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(bind, name: str) -> bool:
    return name in inspect(bind).get_table_names()


def _visit_approval_columns(bind) -> set[str]:
    return {c["name"] for c in inspect(bind).get_columns("visit_approvals")}


def upgrade() -> None:
    bind = op.get_bind()
    va_cols = _visit_approval_columns(bind)
    if "actor_type" not in va_cols:
        op.add_column("visit_approvals", sa.Column("actor_type", sa.String(length=20), nullable=False, server_default="ADMIN_USER"))
    if "actor_host_id" not in va_cols:
        op.add_column("visit_approvals", sa.Column("actor_host_id", sa.Integer(), nullable=True))
    if "actor_name" not in va_cols:
        op.add_column("visit_approvals", sa.Column("actor_name", sa.String(length=255), nullable=True))

    if bind.dialect.name != "sqlite":
        insp = inspect(bind)
        fk_names = {fk["name"] for fk in insp.get_foreign_keys("visit_approvals")}
        with op.batch_alter_table("visit_approvals", schema=None) as batch_op:
            if "fk_visit_approvals_actor_host" not in fk_names and "actor_host_id" in _visit_approval_columns(bind):
                batch_op.create_foreign_key("fk_visit_approvals_actor_host", "hosts", ["actor_host_id"], ["id"])

    if not _table_exists(bind, "host_approval_requests"):
        op.create_table(
            "host_approval_requests",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("visit_id", sa.Integer(), nullable=False),
            sa.Column("host_id", sa.Integer(), nullable=False),
            sa.Column("host_email_snapshot", sa.String(length=255), nullable=True),
            sa.Column("token_hash", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
            sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("response", sa.String(length=20), nullable=True),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_for_reason", sa.String(length=20), nullable=False, server_default="INITIAL"),
            sa.ForeignKeyConstraint(["host_id"], ["hosts.id"]),
            sa.ForeignKeyConstraint(["visit_id"], ["visits.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("token_hash"),
        )
        op.create_index(op.f("ix_host_approval_requests_visit_id"), "host_approval_requests", ["visit_id"], unique=False)
        op.create_index(op.f("ix_host_approval_requests_host_id"), "host_approval_requests", ["host_id"], unique=False)
        op.create_index(op.f("ix_host_approval_requests_token_hash"), "host_approval_requests", ["token_hash"], unique=True)
        op.create_index(op.f("ix_host_approval_requests_status"), "host_approval_requests", ["status"], unique=False)
        op.create_index(op.f("ix_host_approval_requests_expires_at"), "host_approval_requests", ["expires_at"], unique=False)

    if not _table_exists(bind, "notifications"):
        op.create_table(
            "notifications",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("notification_type", sa.String(length=50), nullable=False),
            sa.Column("channel", sa.String(length=20), nullable=False, server_default="EMAIL"),
            sa.Column("recipient", sa.String(length=255), nullable=False),
            sa.Column("visit_id", sa.Integer(), nullable=True),
            sa.Column("host_id", sa.Integer(), nullable=True),
            sa.Column("location_id", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="PENDING"),
            sa.Column("subject", sa.String(length=500), nullable=True),
            sa.Column("template_key", sa.String(length=100), nullable=False),
            sa.Column("payload_json", sa.Text(), nullable=True),
            sa.Column("dedupe_key", sa.String(length=200), nullable=False),
            sa.Column("provider_message_id", sa.String(length=255), nullable=True),
            sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("error_code", sa.String(length=100), nullable=True),
            sa.Column("body_preview", sa.Text(), nullable=True),
            sa.Column("dev_action_url", sa.String(length=500), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
            sa.ForeignKeyConstraint(["host_id"], ["hosts.id"]),
            sa.ForeignKeyConstraint(["location_id"], ["locations.id"]),
            sa.ForeignKeyConstraint(["visit_id"], ["visits.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("dedupe_key"),
        )
        op.create_index(op.f("ix_notifications_notification_type"), "notifications", ["notification_type"], unique=False)
        op.create_index(op.f("ix_notifications_visit_id"), "notifications", ["visit_id"], unique=False)
        op.create_index(op.f("ix_notifications_location_id"), "notifications", ["location_id"], unique=False)
        op.create_index(op.f("ix_notifications_status"), "notifications", ["status"], unique=False)
        op.create_index(op.f("ix_notifications_created_at"), "notifications", ["created_at"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    if _table_exists(bind, "notifications"):
        op.drop_index(op.f("ix_notifications_created_at"), table_name="notifications")
        op.drop_index(op.f("ix_notifications_status"), table_name="notifications")
        op.drop_index(op.f("ix_notifications_location_id"), table_name="notifications")
        op.drop_index(op.f("ix_notifications_visit_id"), table_name="notifications")
        op.drop_index(op.f("ix_notifications_notification_type"), table_name="notifications")
        op.drop_table("notifications")

    if _table_exists(bind, "host_approval_requests"):
        op.drop_index(op.f("ix_host_approval_requests_expires_at"), table_name="host_approval_requests")
        op.drop_index(op.f("ix_host_approval_requests_status"), table_name="host_approval_requests")
        op.drop_index(op.f("ix_host_approval_requests_token_hash"), table_name="host_approval_requests")
        op.drop_index(op.f("ix_host_approval_requests_host_id"), table_name="host_approval_requests")
        op.drop_index(op.f("ix_host_approval_requests_visit_id"), table_name="host_approval_requests")
        op.drop_table("host_approval_requests")

    va_cols = _visit_approval_columns(bind)
    if "actor_name" in va_cols:
        op.drop_column("visit_approvals", "actor_name")
    if "actor_host_id" in va_cols:
        op.drop_column("visit_approvals", "actor_host_id")
    if "actor_type" in va_cols:
        op.drop_column("visit_approvals", "actor_type")
