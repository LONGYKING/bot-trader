import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKey


class Backtest(UUIDPrimaryKey, Base):
    __tablename__ = "backtests"

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
    arq_job_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    date_from: Mapped[date] = mapped_column(Date, nullable=False)
    date_to: Mapped[date] = mapped_column(Date, nullable=False)
    initial_capital: Mapped[float] = mapped_column(Numeric(20, 2), nullable=False, default=10000)
    total_trades: Mapped[int | None] = mapped_column(Integer, nullable=True)
    winning_trades: Mapped[int | None] = mapped_column(Integer, nullable=True)
    win_rate: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    total_pnl_pct: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    sharpe_ratio: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    max_drawdown_pct: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    annual_return_pct: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    sheets_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class BacktestTrade(UUIDPrimaryKey, Base):
    __tablename__ = "backtest_trades"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    backtest_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("backtests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    entry_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    exit_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    tenor_days: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    entry_price: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)
    exit_price: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)
    pnl_pct: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    capital_before: Mapped[float | None] = mapped_column(Numeric(20, 2), nullable=True)
    capital_after: Mapped[float | None] = mapped_column(Numeric(20, 2), nullable=True)
    premium_paid: Mapped[float | None] = mapped_column(Numeric(20, 2), nullable=True)
    trade_size: Mapped[float | None] = mapped_column(Numeric(20, 2), nullable=True)
    max_exposure: Mapped[float | None] = mapped_column(Numeric(20, 2), nullable=True)
    regime_at_entry: Mapped[str | None] = mapped_column(String(40), nullable=True)
    rule_trace: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
