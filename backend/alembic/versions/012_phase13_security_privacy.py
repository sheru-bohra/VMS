"""Phase 13: security, privacy, retention, audit integrity

Revision ID: 012
Revises: 011
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(bind, name: str) -> bool:
    return name in inspect(bind).get_table_names()


def _column_exists(bind, table: str, column: str) -> bool:
    return column in [c["name"] for c in inspect(bind).get_columns(table)]


def upgrade() -> None:
    bind = op.get_bind()

    if not _table_exists(bind, "data_retention_policies"):
        op.create_table(
            "data_retention_policies",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("data_category", sa.String(50), nullable=False, index=True),
            sa.Column("scope_type", sa.String(20), nullable=False, default="GLOBAL"),
            sa.Column("location_id", sa.Integer(), sa.ForeignKey("locations.id"), nullable=True),
            sa.Column("retention_days", sa.Integer(), nullable=False),
            sa.Column("action", sa.String(30), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("admin_users.id"), nullable=True),
            sa.Column("updated_by_user_id", sa.Integer(), sa.ForeignKey("admin_users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index(
            "ix_retention_policy_category_scope",
            "data_retention_policies",
            ["data_category", "scope_type", "location_id"],
            unique=True,
        )

    if not _table_exists(bind, "data_retention_runs"):
        op.create_table(
            "data_retention_runs",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("policy_id", sa.Integer(), sa.ForeignKey("data_retention_policies.id"), nullable=False, index=True),
            sa.Column("mode", sa.String(20), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, index=True),
            sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("started_by_user_id", sa.Integer(), sa.ForeignKey("admin_users.id"), nullable=True),
            sa.Column("eligible_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("processed_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("skipped_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("error_summary", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    if not _table_exists(bind, "data_retention_run_dedupe"):
        op.create_table(
            "data_retention_run_dedupe",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("policy_id", sa.Integer(), sa.ForeignKey("data_retention_policies.id"), nullable=False),
            sa.Column("scheduled_date", sa.String(10), nullable=False),
            sa.Column("run_id", sa.Integer(), sa.ForeignKey("data_retention_runs.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("policy_id", "scheduled_date", name="uq_retention_run_dedupe"),
        )

    if not _table_exists(bind, "rate_limit_buckets"):
        op.create_table(
            "rate_limit_buckets",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("key_hash", sa.String(64), nullable=False, index=True),
            sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
            sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False, index=True),
            sa.UniqueConstraint("key_hash", "window_start", name="uq_rate_limit_bucket"),
        )

    if not _table_exists(bind, "audit_integrity_chain"):
        op.create_table(
            "audit_integrity_chain",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("last_sequence", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_hash", sa.String(128), nullable=False, server_default=""),
            sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    if _table_exists(bind, "visitors"):
        if not _column_exists(bind, "visitors", "privacy_state"):
            op.add_column("visitors", sa.Column("privacy_state", sa.String(20), nullable=False, server_default="ACTIVE"))
        if not _column_exists(bind, "visitors", "anonymized_at"):
            op.add_column("visitors", sa.Column("anonymized_at", sa.DateTime(timezone=True), nullable=True))

    if _table_exists(bind, "compliance_documents"):
        for col, coltype in (
            ("storage_state", sa.String(20)),
            ("encrypted", sa.Boolean()),
            ("encryption_version", sa.Integer()),
            ("purged_at", sa.DateTime(timezone=True)),
            ("malware_scan_status", sa.String(30)),
            ("malware_scanned_at", sa.DateTime(timezone=True)),
        ):
            if not _column_exists(bind, "compliance_documents", col):
                if col == "encrypted":
                    op.add_column("compliance_documents", sa.Column(col, coltype, nullable=False, server_default="0"))
                elif col == "encryption_version":
                    op.add_column("compliance_documents", sa.Column(col, coltype, nullable=True))
                else:
                    op.add_column("compliance_documents", sa.Column(col, coltype, nullable=True))

    if _table_exists(bind, "audit_events"):
        for col in ("integrity_sequence", "previous_integrity_hash", "integrity_hash", "integrity_version"):
            if not _column_exists(bind, "audit_events", col):
                if col == "integrity_sequence":
                    op.add_column("audit_events", sa.Column(col, sa.Integer(), nullable=True, index=True))
                elif col == "integrity_version":
                    op.add_column("audit_events", sa.Column(col, sa.Integer(), nullable=True))
                else:
                    op.add_column("audit_events", sa.Column(col, sa.String(128), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    for table in (
        "rate_limit_buckets",
        "data_retention_run_dedupe",
        "data_retention_runs",
        "data_retention_policies",
        "audit_integrity_chain",
    ):
        if _table_exists(bind, table):
            op.drop_table(table)
    if _table_exists(bind, "visitors"):
        for col in ("anonymized_at", "privacy_state"):
            if _column_exists(bind, "visitors", col):
                op.drop_column("visitors", col)
    if _table_exists(bind, "compliance_documents"):
        for col in (
            "malware_scanned_at",
            "malware_scan_status",
            "purged_at",
            "encryption_version",
            "encrypted",
            "storage_state",
        ):
            if _column_exists(bind, "compliance_documents", col):
                op.drop_column("compliance_documents", col)
    if _table_exists(bind, "audit_events"):
        for col in ("integrity_version", "integrity_hash", "previous_integrity_hash", "integrity_sequence"):
            if _column_exists(bind, "audit_events", col):
                op.drop_column("audit_events", col)
