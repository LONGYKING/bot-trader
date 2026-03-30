from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class SignalResponse(BaseModel):
    id: UUID
    strategy_id: UUID
    asset: str
    timeframe: str
    signal_value: int
    direction: str | None
    tenor_days: int | None
    confidence: float | None
    regime: str | None
    entry_price: float | None
    entry_time: datetime
    expiry_time: datetime | None
    indicator_snapshot: dict | None
    rule_triggered: str | None
    is_profitable: bool | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SignalGenerateRequest(BaseModel):
    strategy_id: UUID


class SignalForceRequest(BaseModel):
    strategy_id: UUID
    signal_value: int = 7       # -7, -3, 3, or 7
    entry_price: float | None = None  # optional — skips market data fetch if provided


class SignalListParams(BaseModel):
    strategy_id: UUID | None = None
    asset: str | None = None
    signal_value: int | None = None
    from_dt: datetime | None = None
    to_dt: datetime | None = None
    is_profitable: bool | None = None
