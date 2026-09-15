"""Phase 2: public registration, hosts, visit extensions

Revision ID: 002
Revises: 001
Create Date: 2026-08-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("locations", sa.Column("public_registration_token", sa.String(length=64), nullable=True))
    op.add_column("locations", sa.Column("registration_enabled", sa.Boolean(), nullable=False, server_default="1"))
    op.create_index(op.f("ix_locations_public_registration_token"), "locations", ["public_registration_token"], unique=True)

    op.create_table(
        "hosts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("department", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_development_seed", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "host_location_assignments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("host_id", sa.Integer(), nullable=False),
        sa.Column("location_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["host_id"], ["hosts.id"]),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_host_location_assignments_host_id"), "host_location_assignments", ["host_id"], unique=False)
    op.create_index(op.f("ix_host_location_assignments_location_id"), "host_location_assignments", ["location_id"], unique=False)

    with op.batch_alter_table("visits", schema=None) as batch_op:
        batch_op.add_column(sa.Column("registration_reference", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("host_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("expected_duration_minutes", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("policy_accepted", sa.Boolean(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("policy_accepted_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("policy_version", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("source", sa.String(length=50), nullable=True))
        batch_op.create_index(batch_op.f("ix_visits_registration_reference"), ["registration_reference"], unique=True)
        batch_op.create_index(batch_op.f("ix_visits_host_id"), ["host_id"], unique=False)
        batch_op.create_foreign_key("fk_visits_host_id", "hosts", ["host_id"], ["id"])


def downgrade() -> None:
    with op.batch_alter_table("visits", schema=None) as batch_op:
        batch_op.drop_constraint("fk_visits_host_id", type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_visits_host_id"))
        batch_op.drop_index(batch_op.f("ix_visits_registration_reference"))
        batch_op.drop_column("source")
        batch_op.drop_column("policy_version")
        batch_op.drop_column("policy_accepted_at")
        batch_op.drop_column("policy_accepted")
        batch_op.drop_column("expected_duration_minutes")
        batch_op.drop_column("host_id")
        batch_op.drop_column("registration_reference")

    op.drop_index(op.f("ix_host_location_assignments_location_id"), table_name="host_location_assignments")
    op.drop_index(op.f("ix_host_location_assignments_host_id"), table_name="host_location_assignments")
    op.drop_table("host_location_assignments")
    op.drop_table("hosts")

    op.drop_index(op.f("ix_locations_public_registration_token"), table_name="locations")
    op.drop_column("locations", "registration_enabled")
    op.drop_column("locations", "public_registration_token")
