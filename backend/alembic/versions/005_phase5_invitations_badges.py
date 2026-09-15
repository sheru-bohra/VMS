"""Phase 5: advance invitations and visitor badges

Revision ID: 005
Revises: 004
Create Date: 2026-08-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _visit_columns(bind) -> set[str]:
    return {c["name"] for c in inspect(bind).get_columns("visits")}


def _table_exists(bind, name: str) -> bool:
    return name in inspect(bind).get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    if _table_exists(bind, "_alembic_tmp_visits"):
        op.drop_table("_alembic_tmp_visits")

    visit_cols = _visit_columns(bind)

    visit_additions = [
        ("notes", sa.Column("notes", sa.Text(), nullable=True)),
        ("scheduled_start", sa.Column("scheduled_start", sa.DateTime(timezone=True), nullable=True)),
        ("scheduled_end", sa.Column("scheduled_end", sa.DateTime(timezone=True), nullable=True)),
        ("created_by_user_id", sa.Column("created_by_user_id", sa.Integer(), nullable=True)),
        ("invitation_token", sa.Column("invitation_token", sa.String(length=64), nullable=True)),
        ("invitation_valid_from", sa.Column("invitation_valid_from", sa.DateTime(timezone=True), nullable=True)),
        ("invitation_valid_until", sa.Column("invitation_valid_until", sa.DateTime(timezone=True), nullable=True)),
        ("invitation_active", sa.Column("invitation_active", sa.Boolean(), nullable=False, server_default="0")),
        ("cancelled_at", sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True)),
        ("cancelled_by_user_id", sa.Column("cancelled_by_user_id", sa.Integer(), nullable=True)),
        ("cancellation_reason", sa.Column("cancellation_reason", sa.Text(), nullable=True)),
    ]
    for name, col in visit_additions:
        if name not in visit_cols:
            op.add_column("visits", col)

    visit_cols = _visit_columns(bind)
    insp = inspect(bind)
    visit_indexes = {idx["name"] for idx in insp.get_indexes("visits")}
    if "ix_visits_scheduled_start" not in visit_indexes:
        op.create_index(op.f("ix_visits_scheduled_start"), "visits", ["scheduled_start"], unique=False)
    if "ix_visits_invitation_token" not in visit_indexes:
        op.create_index(op.f("ix_visits_invitation_token"), "visits", ["invitation_token"], unique=True)

    if bind.dialect.name != "sqlite":
        insp = inspect(bind)
        fk_names = {fk["name"] for fk in insp.get_foreign_keys("visits")}
        visit_cols = _visit_columns(bind)
        with op.batch_alter_table("visits", schema=None) as batch_op:
            if "fk_visits_created_by" not in fk_names and "created_by_user_id" in visit_cols:
                batch_op.create_foreign_key("fk_visits_created_by", "admin_users", ["created_by_user_id"], ["id"])
            if "fk_visits_cancelled_by" not in fk_names and "cancelled_by_user_id" in visit_cols:
                batch_op.create_foreign_key("fk_visits_cancelled_by", "admin_users", ["cancelled_by_user_id"], ["id"])

    if not _table_exists(bind, "visitor_badges"):
        op.create_table(
            "visitor_badges",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("visit_id", sa.Integer(), nullable=False),
            sa.Column("badge_number", sa.String(length=50), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("issued_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
            sa.Column("issued_by_user_id", sa.Integer(), nullable=True),
            sa.Column("printed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("print_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
            sa.ForeignKeyConstraint(["issued_by_user_id"], ["admin_users.id"]),
            sa.ForeignKeyConstraint(["visit_id"], ["visits.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("badge_number"),
        )
        op.create_index(op.f("ix_visitor_badges_visit_id"), "visitor_badges", ["visit_id"], unique=False)
        op.create_index(op.f("ix_visitor_badges_badge_number"), "visitor_badges", ["badge_number"], unique=True)
        op.create_index(op.f("ix_visitor_badges_status"), "visitor_badges", ["status"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    if _table_exists(bind, "visitor_badges"):
        op.drop_index(op.f("ix_visitor_badges_status"), table_name="visitor_badges")
        op.drop_index(op.f("ix_visitor_badges_badge_number"), table_name="visitor_badges")
        op.drop_index(op.f("ix_visitor_badges_visit_id"), table_name="visitor_badges")
        op.drop_table("visitor_badges")

    insp = inspect(bind)
    fk_names = {fk["name"] for fk in insp.get_foreign_keys("visits")}
    if bind.dialect.name != "sqlite":
        with op.batch_alter_table("visits", schema=None) as batch_op:
            if "fk_visits_cancelled_by" in fk_names:
                batch_op.drop_constraint("fk_visits_cancelled_by", type_="foreignkey")
            if "fk_visits_created_by" in fk_names:
                batch_op.drop_constraint("fk_visits_created_by", type_="foreignkey")

    visit_indexes = {idx["name"] for idx in insp.get_indexes("visits")}
    if "ix_visits_invitation_token" in visit_indexes:
        op.drop_index(op.f("ix_visits_invitation_token"), table_name="visits")
    if "ix_visits_scheduled_start" in visit_indexes:
        op.drop_index(op.f("ix_visits_scheduled_start"), table_name="visits")

    visit_cols = _visit_columns(bind)
    for name in (
        "cancellation_reason",
        "cancelled_by_user_id",
        "cancelled_at",
        "invitation_active",
        "invitation_valid_until",
        "invitation_valid_from",
        "invitation_token",
        "created_by_user_id",
        "scheduled_end",
        "scheduled_start",
        "notes",
    ):
        if name in visit_cols:
            op.drop_column("visits", name)
