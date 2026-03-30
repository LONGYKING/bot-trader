from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class DeliveryResponse(BaseModel):
    id: UUID
    signal_id: UUID
    subscription_id: UUID
    channel_id: UUID
    status: str
    attempt_count: int
    last_attempt_at: datetime | None
    delivered_at: datetime | None
    error_message: str | None
    external_msg_id: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
