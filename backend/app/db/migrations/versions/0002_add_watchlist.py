"""Add user_watchlists table

Revision ID: 0002
Revises: 0001
Create Date: 2025-01-01 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_watchlists",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("market", sa.String(10), nullable=False),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("user_id", "ticker", name="uq_watchlist_user_ticker"),
    )
    op.create_index("ix_user_watchlists_user_id", "user_watchlists", ["user_id"])


def downgrade() -> None:
    op.drop_table("user_watchlists")
