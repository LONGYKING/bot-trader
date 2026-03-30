from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ChannelCreate(BaseModel):
    name: str
    channel_type: str  # telegram|slack|discord|whatsapp|email|webhook
    config: dict       # credentials — will be encrypted at rest


class ChannelUpdate(BaseModel):
    name: str | None = None
    config: dict | None = None
    is_active: bool | None = None


class ChannelResponse(BaseModel):
    id: UUID
    name: str
    channel_type: str
    is_active: bool
    last_health_at: datetime | None
    last_health_ok: bool | None
    created_at: datetime
    # config intentionally omitted — sensitive

    model_config = {"from_attributes": True}


class ChannelTestResponse(BaseModel):
    success: bool
    message: str
