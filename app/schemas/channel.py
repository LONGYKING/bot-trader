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
    config_summary: str | None = None  # non-sensitive identifier, e.g. chat_id or webhook domain

    model_config = {"from_attributes": True}

    @classmethod
    def from_channel(cls, channel: object) -> "ChannelResponse":
        """Build response with a safe config summary (no credentials)."""
        cfg = getattr(channel, "config", None) or {}
        summary = _config_summary(getattr(channel, "channel_type", ""), cfg)
        return cls(
            id=channel.id,  # type: ignore[attr-defined]
            name=channel.name,  # type: ignore[attr-defined]
            channel_type=channel.channel_type,  # type: ignore[attr-defined]
            is_active=channel.is_active,  # type: ignore[attr-defined]
            last_health_at=channel.last_health_at,  # type: ignore[attr-defined]
            last_health_ok=channel.last_health_ok,  # type: ignore[attr-defined]
            created_at=channel.created_at,  # type: ignore[attr-defined]
            config_summary=summary,
        )


def _config_summary(channel_type: str, config: dict) -> str | None:
    """Return a non-sensitive one-liner describing the channel destination."""
    if channel_type == "telegram":
        chat_id = config.get("chat_id") or config.get("channel_id")
        return f"chat {chat_id}" if chat_id else None
    if channel_type == "slack":
        ch = config.get("channel") or config.get("channel_name")
        return f"#{ch}" if ch else None
    if channel_type == "discord":
        ch = config.get("channel_id") or config.get("channel")
        return f"channel {ch}" if ch else None
    if channel_type == "email":
        to = config.get("to") or config.get("recipient") or config.get("email")
        return str(to) if to else None
    if channel_type == "webhook":
        url = config.get("url", "")
        try:
            from urllib.parse import urlparse
            return urlparse(url).netloc or url[:40]
        except Exception:
            return url[:40] if url else None
    if channel_type == "whatsapp":
        num = config.get("to") or config.get("phone_number")
        return str(num) if num else None
    return None


class ChannelTestResponse(BaseModel):
    success: bool
    message: str
