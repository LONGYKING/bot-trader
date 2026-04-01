from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.types.subscription import SubscriptionPreferences


class SubscriptionCreate(BaseModel):
    channel_id: UUID
    strategy_id: UUID | None = None
    asset_filter: list[str] | None = None
    signal_filter: list[int] | None = None
    min_confidence: float = Field(0.0, ge=0.0, le=1.0)
    preferences: SubscriptionPreferences = Field(default_factory=SubscriptionPreferences)  # type: ignore[arg-type]


class SubscriptionUpdate(BaseModel):
    strategy_id: UUID | None = None
    asset_filter: list[str] | None = None
    signal_filter: list[int] | None = None
    min_confidence: float | None = None
    preferences: SubscriptionPreferences | None = None
    is_active: bool | None = None


class SubscriptionResponse(BaseModel):
    id: UUID
    channel_id: UUID
    strategy_id: UUID | None
    asset_filter: list[str] | None
    signal_filter: list[int] | None
    min_confidence: float
    preferences: SubscriptionPreferences
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
