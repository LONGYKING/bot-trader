import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKey


class Plan(UUIDPrimaryKey, TimestampMixin, Base):
    """
    Database-driven plan configuration.
    -1 = unlimited, 0 = feature disabled, N = hard cap.
    Edit via admin API — no code changes or restarts needed.
    """

    __tablename__ = "plans"

    key: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price_monthly_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # provider_price_ids: {"stripe": "price_abc", "paddle": "pri_xyz", "lemonsqueezy": "variant_123"}
    provider_price_ids: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # ── Capacity limits ───────────────────────────────────────────────────────
    max_strategies: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    max_channels: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    max_api_keys: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    max_backtests_per_month: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    max_signals_per_day: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    max_signals_per_month: Mapped[int] = mapped_column(Integer, nullable=False, default=100)

    # ── Feature gates ─────────────────────────────────────────────────────────
    # null = all allowed; JSON array = allowlist
    allowed_strategy_classes: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    allowed_channel_types: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)

    can_backtest: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    can_create_api_keys: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    can_use_exchange_channels: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Tenant(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    plan_key: Mapped[str] = mapped_column(
        String(50), ForeignKey("plans.key", ondelete="RESTRICT"), nullable=False, default="free"
    )
    plan_status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    plan_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Payment provider fields (populated on first checkout)
    payment_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    provider_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    provider_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    users: Mapped[list["User"]] = relationship("User", back_populates="tenant", lazy="noload")
    override: Mapped["TenantOverride | None"] = relationship(
        "TenantOverride", back_populates="tenant", uselist=False, lazy="noload"
    )


class User(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "users"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_owner: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="users", lazy="noload")


class TenantOverride(UUIDPrimaryKey, TimestampMixin, Base):
    """
    Per-tenant custom limits. null = inherit from plan. Takes priority over plan.
    Use for custom enterprise deals, beta testers, support exceptions.
    """

    __tablename__ = "tenant_overrides"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # All nullable — null means "inherit from plan"
    max_strategies: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_channels: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_api_keys: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_backtests_per_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_signals_per_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_signals_per_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    allowed_strategy_classes: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    allowed_channel_types: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    can_backtest: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    can_create_api_keys: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    can_use_exchange_channels: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="override", lazy="noload")
