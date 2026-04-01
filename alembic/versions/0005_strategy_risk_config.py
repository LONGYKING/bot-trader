"""Add risk_config JSONB to strategies; add preferences JSONB to subscriptions.

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-31
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "strategies",
        sa.Column("risk_config", JSONB(), nullable=False, server_default="{}"),
    )
    op.add_column(
        "subscriptions",
        sa.Column("preferences", JSONB(), nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("strategies", "risk_config")
    op.drop_column("subscriptions", "preferences")
