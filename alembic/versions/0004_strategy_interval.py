"""Add interval_minutes to strategies.

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-30
"""
import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "strategies",
        sa.Column("interval_minutes", sa.Integer(), nullable=False, server_default="15"),
    )


def downgrade() -> None:
    op.drop_column("strategies", "interval_minutes")
