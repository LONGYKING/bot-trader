"""Add delivery_metadata JSONB to signal_deliveries.

Revision ID: 0006
Revises: 0005
Create Date: 2026-03-31
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "signal_deliveries",
        sa.Column("delivery_metadata", JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("signal_deliveries", "delivery_metadata")
