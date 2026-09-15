"""Phase 14: physical access control and badge printer integration

Revision ID: 013
Revises: 012
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(bind, name: str) -> bool:
    return name in inspect(bind).get_table_names()


def upgrade() -> None:
    bind = op.get_bind()

    if not _table_exists(bind, "location_access_configurations"):
        op.create_table(
            "location_access_configurations",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("location_id", sa.Integer(), sa.ForeignKey("locations.id"), nullable=False, unique=True),
            sa.Column("access_control_enabled", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("provider_key", sa.String(50), nullable=False, server_default="disabled"),
            sa.Column("default_access_profile_id", sa.Integer(), nullable=True),
            sa.Column("credential_grace_minutes", sa.Integer(), nullable=False, server_default="30"),
            sa.Column("max_credential_duration_minutes", sa.Integer(), nullable=False, server_default="720"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    if not _table_exists(bind, "access_profiles"):
        op.create_table(
            "access_profiles",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("location_id", sa.Integer(), sa.ForeignKey("locations.id"), nullable=False, index=True),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("provider_external_profile_ref", sa.String(255), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    if not _table_exists(bind, "visitor_type_access_profiles"):
        op.create_table(
            "visitor_type_access_profiles",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("location_id", sa.Integer(), sa.ForeignKey("locations.id"), nullable=False, index=True),
            sa.Column("visitor_type_id", sa.Integer(), sa.ForeignKey("visitor_types.id"), nullable=False, index=True),
            sa.Column("access_profile_id", sa.Integer(), sa.ForeignKey("access_profiles.id"), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("location_id", "visitor_type_id", name="uq_visitor_type_access_profile"),
        )

    if not _table_exists(bind, "visitor_access_credentials"):
        op.create_table(
            "visitor_access_credentials",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("visit_id", sa.Integer(), sa.ForeignKey("visits.id"), nullable=False, index=True),
            sa.Column("visitor_id", sa.Integer(), sa.ForeignKey("visitors.id"), nullable=False, index=True),
            sa.Column("location_id", sa.Integer(), sa.ForeignKey("locations.id"), nullable=False, index=True),
            sa.Column("access_profile_id", sa.Integer(), sa.ForeignKey("access_profiles.id"), nullable=True),
            sa.Column("status", sa.String(30), nullable=False, index=True),
            sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
            sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True, index=True),
            sa.Column("provider_key", sa.String(50), nullable=False),
            sa.Column("provider_credential_reference", sa.String(255), nullable=True),
            sa.Column("provisioned_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("expired_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_error_code", sa.String(100), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    if not _table_exists(bind, "access_provisioning_attempts"):
        op.create_table(
            "access_provisioning_attempts",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("access_credential_id", sa.Integer(), sa.ForeignKey("visitor_access_credentials.id"), nullable=False, index=True),
            sa.Column("action", sa.String(30), nullable=False),
            sa.Column("status", sa.String(30), nullable=False, index=True),
            sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("dedupe_key", sa.String(100), nullable=False, unique=True),
            sa.Column("available_at", sa.DateTime(timezone=True), server_default=sa.func.now(), index=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("error_code", sa.String(100), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    if not _table_exists(bind, "badge_printers"):
        op.create_table(
            "badge_printers",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("location_id", sa.Integer(), sa.ForeignKey("locations.id"), nullable=False, index=True),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("provider_key", sa.String(50), nullable=False),
            sa.Column("provider_external_printer_ref", sa.String(255), nullable=False),
            sa.Column("is_default", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    if not _table_exists(bind, "badge_print_jobs"):
        op.create_table(
            "badge_print_jobs",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("visitor_badge_id", sa.Integer(), sa.ForeignKey("visitor_badges.id"), nullable=False, index=True),
            sa.Column("visit_id", sa.Integer(), sa.ForeignKey("visits.id"), nullable=False, index=True),
            sa.Column("location_id", sa.Integer(), sa.ForeignKey("locations.id"), nullable=False, index=True),
            sa.Column("printer_id", sa.Integer(), sa.ForeignKey("badge_printers.id"), nullable=False),
            sa.Column("status", sa.String(30), nullable=False, index=True),
            sa.Column("requested_by_user_id", sa.Integer(), sa.ForeignKey("admin_users.id"), nullable=True),
            sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("idempotency_key", sa.String(100), nullable=True, unique=True),
            sa.Column("queued_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("printed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("provider_job_reference", sa.String(255), nullable=True),
            sa.Column("last_error_code", sa.String(100), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )


def downgrade() -> None:
    op.drop_table("badge_print_jobs")
    op.drop_table("badge_printers")
    op.drop_table("access_provisioning_attempts")
    op.drop_table("visitor_access_credentials")
    op.drop_table("visitor_type_access_profiles")
    op.drop_table("access_profiles")
    op.drop_table("location_access_configurations")
