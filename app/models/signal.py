import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKey


class Signal(UUIDPrimaryKey, Base):
    __tablename__ = "signals"
    __table_args__ = (
        CheckConstraint("signal_value IN (-7, -3, 0, 3, 7)", name="ck_signals_signal_value"),
        UniqueConstraint("strategy_id", "asset", "entry_time", name="uq_signal_strategy_entry"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    strategy_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("strategies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    asset: Mapped[str] = mapped_column(String(50), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False)
    signal_value: Mapped[int] = mapped_column(SmallInteger, nullable=False, index=True)
    trade_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    direction: Mapped[str | None] = mapped_column(String(10), nullable=True)
    tenor_days: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    profit_cap_pct: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    regime: Mapped[str | None] = mapped_column(String(40), nullable=True)
    entry_price: Mapped[float | None] = mapped_column(Numeric(20, 8), nullable=True)
    entry_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    expiry_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    indicator_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    rule_triggered: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_profitable: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
