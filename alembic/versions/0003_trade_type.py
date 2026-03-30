"""Add trade_type and execution_params to strategies; add trade_type to signals.

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # strategies: add trade_type and execution_params
    op.add_column(
        "strategies",
        sa.Column("trade_type", sa.String(20), nullable=False, server_default="options"),
    )
    op.add_column(
        "strategies",
        sa.Column("execution_params", JSONB, nullable=False, server_default="{}"),
    )

    # signals: add trade_type (nullable — existing rows represent options trades)
    op.add_column(
        "signals",
        sa.Column("trade_type", sa.String(20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("signals", "trade_type")
    op.drop_column("strategies", "execution_params")
    op.drop_column("strategies", "trade_type")
