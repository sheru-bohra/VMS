"""Direct owner authentication credentials

Revision ID: 017
Revises: 016
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "017"
down_revision: Union[str, None] = "016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(bind, table: str, column: str) -> bool:
    return column in {c["name"] for c in inspect(bind).get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    if not _column_exists(bind, "admin_users", "password_hash"):
        op.add_column("admin_users", sa.Column("password_hash", sa.String(length=255), nullable=True))
    if not _column_exists(bind, "admin_users", "password_changed_at"):
        op.add_column(
            "admin_users",
            sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True),
        )
    if not _column_exists(bind, "admin_users", "failed_login_count"):
        op.add_column(
            "admin_users",
            sa.Column("failed_login_count", sa.Integer(), nullable=False, server_default="0"),
        )
    if not _column_exists(bind, "admin_users", "locked_until"):
        op.add_column(
            "admin_users",
            sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        )
    if not _column_exists(bind, "admin_users", "direct_owner_sessions_valid_after"):
        op.add_column(
            "admin_users",
            sa.Column("direct_owner_sessions_valid_after", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if _column_exists(bind, "admin_users", "direct_owner_sessions_valid_after"):
        op.drop_column("admin_users", "direct_owner_sessions_valid_after")
    if _column_exists(bind, "admin_users", "locked_until"):
        op.drop_column("admin_users", "locked_until")
    if _column_exists(bind, "admin_users", "failed_login_count"):
        op.drop_column("admin_users", "failed_login_count")
    if _column_exists(bind, "admin_users", "password_changed_at"):
        op.drop_column("admin_users", "password_changed_at")
    if _column_exists(bind, "admin_users", "password_hash"):
        op.drop_column("admin_users", "password_hash")
