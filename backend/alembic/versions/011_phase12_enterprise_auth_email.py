"""Phase 12: Entra identity linkage and auth metadata

Revision ID: 011
Revises: 010
Create Date: 2026-08-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(bind, name: str) -> bool:
    return name in inspect(bind).get_table_names()


def _column_exists(bind, table: str, column: str) -> bool:
    return column in [c["name"] for c in inspect(bind).get_columns(table)]


def upgrade() -> None:
    bind = op.get_bind()
    if _table_exists(bind, "admin_users"):
        if not _column_exists(bind, "admin_users", "entra_tenant_id"):
            op.add_column("admin_users", sa.Column("entra_tenant_id", sa.String(length=64), nullable=True))
        if not _column_exists(bind, "admin_users", "entra_object_id"):
            op.add_column("admin_users", sa.Column("entra_object_id", sa.String(length=64), nullable=True))
        if not _column_exists(bind, "admin_users", "auth_provider"):
            op.add_column("admin_users", sa.Column("auth_provider", sa.String(length=20), nullable=True))
        if not _column_exists(bind, "admin_users", "identity_linked_at"):
            op.add_column("admin_users", sa.Column("identity_linked_at", sa.DateTime(timezone=True), nullable=True))
        if not _column_exists(bind, "admin_users", "last_login_at"):
            op.add_column("admin_users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
        op.create_index(
            "ix_admin_users_entra_identity",
            "admin_users",
            ["entra_tenant_id", "entra_object_id"],
            unique=True,
        )


def downgrade() -> None:
    bind = op.get_bind()
    if _table_exists(bind, "admin_users"):
        try:
            op.drop_index("ix_admin_users_entra_identity", table_name="admin_users")
        except Exception:
            pass
        for col in ("last_login_at", "identity_linked_at", "auth_provider", "entra_object_id", "entra_tenant_id"):
            if _column_exists(bind, "admin_users", col):
                op.drop_column("admin_users", col)
