"""Track owner initial credential provisioning

Revision ID: 019
Revises: 018
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "019"
down_revision: Union[str, None] = "018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(bind, table: str, column: str) -> bool:
    return column in {c["name"] for c in inspect(bind).get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    if not _column_exists(bind, "admin_users", "initial_credential_provisioned_at"):
        op.add_column(
            "admin_users",
            sa.Column("initial_credential_provisioned_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if _column_exists(bind, "admin_users", "initial_credential_provisioned_at"):
        op.drop_column("admin_users", "initial_credential_provisioned_at")
