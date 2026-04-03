"""Channel management service."""
import importlib
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.channel import Channel
from app.repositories.channel import ChannelRepository

_KNOWN_CHANNEL_TYPES: dict[str, str] = {
    "telegram": "telegram.TelegramChannel",
    "discord": "discord.DiscordChannel",
    "slack": "slack.SlackChannel",
    "webhook": "webhook.WebhookChannel",
    "email": "email.EmailChannel",
    "exchange": "exchange.ExchangeChannel",
}


def _load_channel_class(channel_type: str):
    path = _KNOWN_CHANNEL_TYPES.get(channel_type)
    if path is None:
        return None
    module_name, class_name = path.rsplit(".", 1)
    try:
        mod = importlib.import_module(f"app.channels.{module_name}")
        return getattr(mod, class_name, None)
    except ImportError:
        return None


def _validate_channel_type(channel_type: str) -> None:
    if channel_type not in _KNOWN_CHANNEL_TYPES:
        raise ValidationError(
            f"Unknown channel_type '{channel_type}'. "
            f"Valid types: {sorted(_KNOWN_CHANNEL_TYPES.keys())}"
        )


async def create_channel(
    session: AsyncSession,
    data: dict[str, Any],
    tenant_id: uuid.UUID | None = None,
) -> Channel:
    channel_type = data.get("channel_type", "")
    _validate_channel_type(channel_type)

    repo = ChannelRepository(session, tenant_id)
    existing = await repo.get_by_name(data.get("name", ""))
    if existing is not None:
        raise ConflictError(f"Channel with name '{data['name']}' already exists")

    return await repo.create(data)


async def get_channel(
    session: AsyncSession,
    id: uuid.UUID,
    tenant_id: uuid.UUID | None = None,
) -> Channel:
    repo = ChannelRepository(session, tenant_id)
    channel = await repo.get_by_id(id)
    if channel is None:
        raise NotFoundError("Channel", str(id))
    return channel


async def list_channels(
    session: AsyncSession,
    tenant_id: uuid.UUID | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[Channel]:
    repo = ChannelRepository(session, tenant_id)
    return await repo.list_active(limit=limit, offset=offset)


async def update_channel(
    session: AsyncSession,
    id: uuid.UUID,
    data: dict[str, Any],
    tenant_id: uuid.UUID | None = None,
) -> Channel:
    repo = ChannelRepository(session, tenant_id)
    channel = await repo.get_by_id(id)
    if channel is None:
        raise NotFoundError("Channel", str(id))

    if "channel_type" in data:
        _validate_channel_type(data["channel_type"])

    if "name" in data and data["name"] != channel.name:
        existing = await repo.get_by_name(data["name"])
        if existing is not None:
            raise ConflictError(f"Channel with name '{data['name']}' already exists")

    updated = await repo.update(id, data)
    if updated is None:
        raise NotFoundError("Channel", str(id))
    return updated


async def delete_channel(
    session: AsyncSession,
    id: uuid.UUID,
    tenant_id: uuid.UUID | None = None,
) -> None:
    repo = ChannelRepository(session, tenant_id)
    channel = await repo.get_by_id(id)
    if channel is None:
        raise NotFoundError("Channel", str(id))
    deleted = await repo.delete(id)
    if not deleted:
        raise NotFoundError("Channel", str(id))


async def test_channel(
    session: AsyncSession,
    id: uuid.UUID,
    tenant_id: uuid.UUID | None = None,
) -> dict:
    channel = await get_channel(session, id, tenant_id=tenant_id)
    cls = _load_channel_class(channel.channel_type)
    if cls is None:
        return {
            "success": False,
            "error": f"Channel type '{channel.channel_type}' is not implemented yet.",
        }
    try:
        instance = cls(channel.config)
        result = await instance.send_test()
        if result.success:
            return {"success": True, "message": "Test message sent successfully."}
        return {"success": False, "message": result.error or "Send failed with no error detail."}
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "message": str(exc)}


async def check_channel_health(
    session: AsyncSession,
    id: uuid.UUID,
    tenant_id: uuid.UUID | None = None,
) -> dict:
    repo = ChannelRepository(session, tenant_id)
    channel = await get_channel(session, id, tenant_id=tenant_id)
    cls = _load_channel_class(channel.channel_type)

    ok = False
    error: str | None = None

    if cls is None:
        error = (
            f"Channel type '{channel.channel_type}' is not implemented; "
            "health check cannot be performed."
        )
    else:
        try:
            instance = cls(channel.config)
            ok = await instance.health_check()
        except Exception as exc:  # noqa: BLE001
            ok = False
            error = str(exc)

    await repo.update_health(id, ok)

    return {"channel_id": str(id), "healthy": ok, "error": error}
