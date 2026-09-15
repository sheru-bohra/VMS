"""Register visitor extended fields

Revision ID: 015
Revises: 014
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(bind, table: str, column: str) -> bool:
    return column in {c["name"] for c in inspect(bind).get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()

    if not _column_exists(bind, "visitors", "designation"):
        op.add_column("visitors", sa.Column("designation", sa.String(255), nullable=True))
    if not _column_exists(bind, "visitors", "address"):
        op.add_column("visitors", sa.Column("address", sa.Text(), nullable=True))

    if not _column_exists(bind, "visits", "registration_metadata_json"):
        op.add_column("visits", sa.Column("registration_metadata_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    if _column_exists(bind, "visits", "registration_metadata_json"):
        op.drop_column("visits", "registration_metadata_json")
    if _column_exists(bind, "visitors", "address"):
        op.drop_column("visitors", "address")
    if _column_exists(bind, "visitors", "designation"):
        op.drop_column("visitors", "designation")
