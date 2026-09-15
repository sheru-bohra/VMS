"""Phase 3: visit approval history

Revision ID: 003
Revises: 002
Create Date: 2026-08-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "visit_approvals",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("visit_id", sa.Integer(), nullable=False),
        sa.Column("decision", sa.String(length=20), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("actor_email", sa.String(length=255), nullable=True),
        sa.Column("actor_role", sa.String(length=50), nullable=True),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("reason_code", sa.String(length=50), nullable=True),
        sa.Column("previous_status", sa.String(length=50), nullable=False),
        sa.Column("new_status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["admin_users.id"]),
        sa.ForeignKeyConstraint(["site_id"], ["locations.id"]),
        sa.ForeignKeyConstraint(["visit_id"], ["visits.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_visit_approvals_visit_id"), "visit_approvals", ["visit_id"], unique=False)
    op.create_index(op.f("ix_visit_approvals_site_id"), "visit_approvals", ["site_id"], unique=False)
    op.create_index(op.f("ix_visit_approvals_created_at"), "visit_approvals", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_visit_approvals_created_at"), table_name="visit_approvals")
    op.drop_index(op.f("ix_visit_approvals_site_id"), table_name="visit_approvals")
    op.drop_index(op.f("ix_visit_approvals_visit_id"), table_name="visit_approvals")
    op.drop_table("visit_approvals")
