"""Phase 4: multi-location operations metadata

Revision ID: 004
Revises: 003
Create Date: 2026-08-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("locations", sa.Column("city", sa.String(length=100), nullable=True))
    op.add_column("locations", sa.Column("timezone", sa.String(length=64), nullable=True))

    with op.batch_alter_table("visits", schema=None) as batch_op:
        batch_op.add_column(sa.Column("arrived_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("arrival_recorded_by_user_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("arrival_location_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("checked_in_by_user_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("check_in_location_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("check_in_method", sa.String(length=50), nullable=True))
        batch_op.create_foreign_key(
            "fk_visits_arrival_recorded_by",
            "admin_users",
            ["arrival_recorded_by_user_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_visits_arrival_location",
            "locations",
            ["arrival_location_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_visits_checked_in_by",
            "admin_users",
            ["checked_in_by_user_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_visits_check_in_location",
            "locations",
            ["check_in_location_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("visits", schema=None) as batch_op:
        batch_op.drop_constraint("fk_visits_check_in_location", type_="foreignkey")
        batch_op.drop_constraint("fk_visits_checked_in_by", type_="foreignkey")
        batch_op.drop_constraint("fk_visits_arrival_location", type_="foreignkey")
        batch_op.drop_constraint("fk_visits_arrival_recorded_by", type_="foreignkey")
        batch_op.drop_column("check_in_method")
        batch_op.drop_column("check_in_location_id")
        batch_op.drop_column("checked_in_by_user_id")
        batch_op.drop_column("arrival_location_id")
        batch_op.drop_column("arrival_recorded_by_user_id")
        batch_op.drop_column("arrived_at")

    op.drop_column("locations", "timezone")
    op.drop_column("locations", "city")
