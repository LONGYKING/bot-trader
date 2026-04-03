"""Multi-tenancy: plans, tenants, users, tenant_overrides; tenant_id on all tables.

Revision ID: 0007
Revises: 0006
Create Date: 2026-04-01
"""
import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

# ── Revision identifiers ──────────────────────────────────────────────────────

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

# Fixed UUID for the default "legacy" tenant that owns all existing rows
_DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    # ── 1. Plans table ────────────────────────────────────────────────────────
    op.create_table(
        "plans",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("key", sa.String(50), nullable=False, unique=True),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("price_monthly_cents", sa.Integer, nullable=False, server_default="0"),
        sa.Column("provider_price_ids", JSONB, nullable=False, server_default="{}"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("is_public", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        # Capacity limits (-1 = unlimited)
        sa.Column("max_strategies", sa.Integer, nullable=False, server_default="1"),
        sa.Column("max_channels", sa.Integer, nullable=False, server_default="1"),
        sa.Column("max_api_keys", sa.Integer, nullable=False, server_default="2"),
        sa.Column("max_backtests_per_month", sa.Integer, nullable=False, server_default="3"),
        sa.Column("max_signals_per_day", sa.Integer, nullable=False, server_default="10"),
        sa.Column("max_signals_per_month", sa.Integer, nullable=False, server_default="100"),
        # Feature allowlists (NULL = all allowed)
        sa.Column("allowed_strategy_classes", ARRAY(sa.Text), nullable=True),
        sa.Column("allowed_channel_types", ARRAY(sa.Text), nullable=True),
        # Feature flags
        sa.Column("can_backtest", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("can_create_api_keys", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("can_use_exchange_channels", sa.Boolean, nullable=False, server_default="false"),
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Seed default plans
    op.execute("""
        INSERT INTO plans (
            id, key, display_name, description, price_monthly_cents, provider_price_ids,
            is_active, is_public, sort_order,
            max_strategies, max_channels, max_api_keys, max_backtests_per_month,
            max_signals_per_day, max_signals_per_month,
            allowed_strategy_classes, allowed_channel_types,
            can_backtest, can_create_api_keys, can_use_exchange_channels
        ) VALUES
        (gen_random_uuid(), 'free',       'Free',       'Get started for free',         0,      '{}',
         true, true, 1,   1,   1,   2,   3,    10,   100,  NULL, ARRAY['telegram','discord'], true,  true,  false),
        (gen_random_uuid(), 'trader',     'Trader',     'For active traders',          4900,   '{}',
         true, true, 2,   5,   3,   5,   20,   -1,   -1,   NULL, NULL,                        true,  true,  false),
        (gen_random_uuid(), 'pro',        'Pro',        'Full access',                14900,   '{}',
         true, true, 3,   20,  10,  20,  100,  -1,   -1,   NULL, NULL,                        true,  true,  true),
        (gen_random_uuid(), 'enterprise', 'Enterprise', 'Unlimited — contact us',     49900,   '{}',
         true, false, 4,  -1,  -1,  -1,  -1,   -1,   -1,   NULL, NULL,                        true,  true,  true)
    """)

    # ── 2. Tenants table ──────────────────────────────────────────────────────
    op.create_table(
        "tenants",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("plan_key", sa.String(50), nullable=False, server_default="free"),
        sa.Column("plan_status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("plan_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payment_provider", sa.String(50), nullable=True),
        sa.Column("provider_customer_id", sa.String(255), nullable=True),
        sa.Column("provider_subscription_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(["plan_key"], ["plans.key"], ondelete="RESTRICT"),
    )

    # Insert default tenant to own all existing rows
    op.execute(f"""
        INSERT INTO tenants (id, name, plan_key, plan_status)
        VALUES ('{_DEFAULT_TENANT_ID}', 'default', 'enterprise', 'active')
    """)

    # ── 3. Users table ────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("is_owner", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_users_tenant", "users", ["tenant_id"])

    # ── 4. Tenant overrides table ─────────────────────────────────────────────
    op.create_table(
        "tenant_overrides",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("notes", sa.Text, nullable=True),
        # All nullable — null means "inherit from plan"
        sa.Column("max_strategies", sa.Integer, nullable=True),
        sa.Column("max_channels", sa.Integer, nullable=True),
        sa.Column("max_api_keys", sa.Integer, nullable=True),
        sa.Column("max_backtests_per_month", sa.Integer, nullable=True),
        sa.Column("max_signals_per_day", sa.Integer, nullable=True),
        sa.Column("max_signals_per_month", sa.Integer, nullable=True),
        sa.Column("allowed_strategy_classes", ARRAY(sa.Text), nullable=True),
        sa.Column("allowed_channel_types", ARRAY(sa.Text), nullable=True),
        sa.Column("can_backtest", sa.Boolean, nullable=True),
        sa.Column("can_create_api_keys", sa.Boolean, nullable=True),
        sa.Column("can_use_exchange_channels", sa.Boolean, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
    )

    # ── 5. Add tenant_id to all existing tables ────────────────────────────────
    tables = [
        "strategies",
        "signals",
        "channels",
        "subscriptions",
        "signal_deliveries",
        "signal_outcomes",
        "backtests",
        "backtest_trades",
        "api_keys",
    ]

    for table in tables:
        # Add nullable first so we can backfill
        op.add_column(table, sa.Column("tenant_id", UUID(as_uuid=True), nullable=True))
        # Backfill with default tenant
        op.execute(f"UPDATE {table} SET tenant_id = '{_DEFAULT_TENANT_ID}'")
        # Make NOT NULL
        op.alter_column(table, "tenant_id", nullable=False)
        # FK constraint
        op.create_foreign_key(
            f"fk_{table}_tenant_id",
            table,
            "tenants",
            ["tenant_id"],
            ["id"],
            ondelete="CASCADE",
        )
        # Index for fast tenant-scoped queries
        op.create_index(f"idx_{table}_tenant_id", table, ["tenant_id"])

    # ── 6. Tenant-scoped unique indexes ───────────────────────────────────────
    # Drop old global unique constraints (strategies.name, channels.name)
    # using IF EXISTS so the migration is safe regardless of the constraint name
    # (could be "strategies_name_key", "uq_strategies_name", etc.)
    op.execute("ALTER TABLE strategies DROP CONSTRAINT IF EXISTS strategies_name_key")
    op.execute("ALTER TABLE strategies DROP CONSTRAINT IF EXISTS uq_strategies_name")
    op.execute("ALTER TABLE channels DROP CONSTRAINT IF EXISTS channels_name_key")
    op.execute("ALTER TABLE channels DROP CONSTRAINT IF EXISTS uq_channels_name")

    op.create_unique_constraint(
        "uq_strategies_tenant_name", "strategies", ["tenant_id", "name"]
    )
    op.create_unique_constraint(
        "uq_channels_tenant_name", "channels", ["tenant_id", "name"]
    )


def downgrade() -> None:
    # Remove tenant-scoped unique indexes
    op.drop_constraint("uq_strategies_tenant_name", "strategies", type_="unique")
    op.drop_constraint("uq_channels_tenant_name", "channels", type_="unique")

    # Drop tenant_id from all tables
    tables = [
        "strategies", "signals", "channels", "subscriptions",
        "signal_deliveries", "signal_outcomes", "backtests",
        "backtest_trades", "api_keys",
    ]
    for table in tables:
        op.drop_constraint(f"fk_{table}_tenant_id", table, type_="foreignkey")
        op.drop_index(f"idx_{table}_tenant_id", table_name=table)
        op.drop_column(table, "tenant_id")

    # Drop new tables in reverse FK order
    op.drop_table("tenant_overrides")
    op.drop_index("idx_users_tenant", table_name="users")
    op.drop_table("users")
    op.drop_table("tenants")
    op.drop_table("plans")
