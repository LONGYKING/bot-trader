from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class OutcomeResponse(BaseModel):
    id: UUID
    signal_id: UUID
    exit_price: float
    exit_time: datetime
    pnl_pct: float
    is_profitable: bool
    regime_at_exit: str | None
    computed_at: datetime

    model_config = {"from_attributes": True}


class OutcomeStats(BaseModel):
    total_count: int
    winning_count: int
    win_rate: float
    avg_pnl_pct: float
