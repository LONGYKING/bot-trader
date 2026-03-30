from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class BacktestCreate(BaseModel):
    strategy_id: UUID
    date_from: date
    date_to: date
    initial_capital: float = Field(10000.0, gt=0)


class BacktestResponse(BaseModel):
    id: UUID
    strategy_id: UUID
    status: str
    date_from: date
    date_to: date
    initial_capital: float
    total_trades: int | None
    winning_trades: int | None
    win_rate: float | None
    total_pnl_pct: float | None
    sharpe_ratio: float | None
    max_drawdown_pct: float | None
    annual_return_pct: float | None
    sheets_url: str | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class BacktestTradeResponse(BaseModel):
    id: UUID
    backtest_id: UUID
    entry_time: datetime
    exit_time: datetime
    direction: str
    tenor_days: int | None
    entry_price: float
    exit_price: float
    pnl_pct: float
    capital_before: float | None
    capital_after: float | None
    premium_paid: float | None
    trade_size: float | None
    max_exposure: float | None
    regime_at_entry: str | None

    model_config = {"from_attributes": True}
