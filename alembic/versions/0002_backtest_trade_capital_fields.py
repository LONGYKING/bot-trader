"""add capital tracking and trade sizing fields to backtest_trades

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-28 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("backtest_trades", sa.Column("capital_before", sa.Numeric(20, 2), nullable=True))
    op.add_column("backtest_trades", sa.Column("capital_after", sa.Numeric(20, 2), nullable=True))
    op.add_column("backtest_trades", sa.Column("premium_paid", sa.Numeric(20, 2), nullable=True))
    op.add_column("backtest_trades", sa.Column("trade_size", sa.Numeric(20, 2), nullable=True))
    op.add_column("backtest_trades", sa.Column("max_exposure", sa.Numeric(20, 2), nullable=True))


def downgrade() -> None:
    op.drop_column("backtest_trades", "max_exposure")
    op.drop_column("backtest_trades", "trade_size")
    op.drop_column("backtest_trades", "premium_paid")
    op.drop_column("backtest_trades", "capital_after")
    op.drop_column("backtest_trades", "capital_before")
