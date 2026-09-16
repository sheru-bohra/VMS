"""Track owner credential established by user action

Revision ID: 020
Revises: 019
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "020"
down_revision: Union[str, None] = "019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(bind, table: str, column: str) -> bool:
    return column in {c["name"] for c in inspect(bind).get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    if not _column_exists(bind, "admin_users", "owner_password_user_established"):
        op.add_column(
            "admin_users",
            sa.Column(
                "owner_password_user_established",
                sa.Boolean(),
                nullable=False,
                server_default="0",
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if _column_exists(bind, "admin_users", "owner_password_user_established"):
        op.drop_column("admin_users", "owner_password_user_established")
