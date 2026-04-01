from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.types.strategy import StrategyRiskConfig


class StrategyCreate(BaseModel):
    name: str
    strategy_class: str
    description: str | None = None
    asset: str
    timeframe: str
    exchange: str = "binance"
    params: dict = Field(default_factory=dict)
    trade_type: str = "options"
    execution_params: dict = Field(default_factory=dict)
    interval_minutes: int = 15
    risk_config: StrategyRiskConfig = Field(default_factory=StrategyRiskConfig)  # type: ignore[arg-type]


class StrategyUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    params: dict | None = None
    trade_type: str | None = None
    execution_params: dict | None = None
    interval_minutes: int | None = None
    risk_config: StrategyRiskConfig | None = None
    is_active: bool | None = None


class StrategyResponse(BaseModel):
    id: UUID
    name: str
    strategy_class: str
    description: str | None
    asset: str
    timeframe: str
    exchange: str
    params: dict
    trade_type: str
    execution_params: dict
    interval_minutes: int
    risk_config: StrategyRiskConfig
    is_active: bool
    version: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class StrategyPerformance(BaseModel):
    strategy_id: UUID
    total_signals: int
    profitable_signals: int
    win_rate: float
    avg_pnl_pct: float
    by_regime: dict
