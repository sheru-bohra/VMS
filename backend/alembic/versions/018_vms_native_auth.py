"""VMS native staff authentication

Revision ID: 018
Revises: 017
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "018"
down_revision: Union[str, None] = "017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(bind, table: str, column: str) -> bool:
    return column in {c["name"] for c in inspect(bind).get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    if not _column_exists(bind, "admin_users", "force_password_change"):
        op.add_column(
            "admin_users",
            sa.Column("force_password_change", sa.Boolean(), nullable=False, server_default="0"),
        )

    op.execute(
        "UPDATE admin_users SET auth_provider = 'vms_native' "
        "WHERE auth_provider IN ('direct', 'dev') OR auth_provider IS NULL"
    )
    dialect = bind.dialect.name
    true_literal = "TRUE" if dialect == "postgresql" else "1"
    op.execute(
        f"UPDATE admin_users SET force_password_change = {true_literal} "
        f"WHERE password_hash IS NULL AND is_active = {true_literal}"
    )


def downgrade() -> None:
    bind = op.get_bind()
    if _column_exists(bind, "admin_users", "force_password_change"):
        op.drop_column("admin_users", "force_password_change")
