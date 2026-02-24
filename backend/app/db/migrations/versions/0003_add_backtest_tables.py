"""Add backtest tables

Revision ID: 0003
Revises: 0002
Create Date: 2025-01-01 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "backtest_strategies",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", sa.String(255), nullable=True),
        sa.Column("natural_language_input", sa.Text(), nullable=False),
        sa.Column("parsed_strategy", JSONB(), nullable=True),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_backtest_strategies_user_id", "backtest_strategies", ["user_id"])
    op.create_index("ix_backtest_strategies_ticker", "backtest_strategies", ["ticker"])

    op.create_table(
        "backtest_results",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "strategy_id",
            UUID(as_uuid=True),
            sa.ForeignKey("backtest_strategies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("total_return", sa.Float(), nullable=True),
        sa.Column("sharpe_ratio", sa.Float(), nullable=True),
        sa.Column("max_drawdown", sa.Float(), nullable=True),
        sa.Column("win_rate", sa.Float(), nullable=True),
        sa.Column("total_trades", sa.Integer(), nullable=True),
        sa.Column("equity_curve", JSONB(), nullable=True),
        sa.Column("trade_log", JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_backtest_results_strategy_id", "backtest_results", ["strategy_id"]
    )


def downgrade() -> None:
    op.drop_table("backtest_results")
    op.drop_table("backtest_strategies")
