"""Visitor media for local protected photo storage

Revision ID: 016
Revises: 015
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "016"
down_revision: Union[str, None] = "015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(bind, name: str) -> bool:
    return name in inspect(bind).get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, "visitor_media"):
        op.create_table(
            "visitor_media",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("visitor_id", sa.Integer(), sa.ForeignKey("visitors.id"), nullable=True, index=True),
            sa.Column("visit_id", sa.Integer(), sa.ForeignKey("visits.id"), nullable=True, index=True),
            sa.Column("location_id", sa.Integer(), sa.ForeignKey("locations.id"), nullable=True, index=True),
            sa.Column("media_type", sa.String(30), nullable=False, index=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="STAGED", index=True),
            sa.Column("storage_rel_path", sa.String(512), nullable=False),
            sa.Column("stored_filename", sa.String(255), nullable=False),
            sa.Column("original_filename", sa.String(255), nullable=True),
            sa.Column("mime_type", sa.String(100), nullable=False),
            sa.Column("file_size", sa.Integer(), nullable=False),
            sa.Column("source", sa.String(20), nullable=False),
            sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("admin_users.id"), nullable=False),
            sa.Column("retention_category", sa.String(30), nullable=False, server_default="VISITOR_PII"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_visitor_media_status_type", "visitor_media", ["status", "media_type"])


def downgrade() -> None:
    bind = op.get_bind()
    if _table_exists(bind, "visitor_media"):
        op.drop_table("visitor_media")
