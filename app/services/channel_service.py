"""Channel management service.

Channel classes are loaded from the ``app.channels`` package. Each channel class
must implement at minimum:

    async def send_test(self) -> dict  — sends a test message, returns result dict
    async def health_check(self) -> bool  — returns True if healthy

Channel classes are looked up by ``channel_type`` string stored on the model.
"""
import importlib
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.channel import Channel
from app.repositories.channel import ChannelRepository

# Mapping from channel_type string to the module/class within app.channels
_KNOWN_CHANNEL_TYPES: dict[str, str] = {
    "telegram": "telegram.TelegramChannel",
    "discord": "discord.DiscordChannel",
    "slack": "slack.SlackChannel",
    "webhook": "webhook.WebhookChannel",
    "email": "email.EmailChannel",
    "exchange": "exchange.ExchangeChannel",
}


def _load_channel_class(channel_type: str):
    """Dynamically load a channel class from app.channels.<module>.<ClassName>.

    Returns None if the module or class is not yet implemented (graceful degradation
    during development when only some channels exist).
    """
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


async def create_channel(session: AsyncSession, data: dict[str, Any]) -> Channel:
    """Create a new channel. Validates channel_type and name uniqueness."""
    channel_type = data.get("channel_type", "")
    _validate_channel_type(channel_type)

    repo = ChannelRepository(session)
    existing = await repo.get_by_name(data.get("name", ""))
    if existing is not None:
        raise ConflictError(f"Channel with name '{data['name']}' already exists")

    return await repo.create(data)


async def get_channel(session: AsyncSession, id: uuid.UUID) -> Channel:
    """Return a channel by id (config decrypted). Raises NotFoundError if missing."""
    repo = ChannelRepository(session)
    channel = await repo.get_by_id(id)  # decrypts config
    if channel is None:
        raise NotFoundError("Channel", str(id))
    return channel


async def list_channels(session: AsyncSession) -> list[Channel]:
    """Return all active channels with decrypted configs."""
    repo = ChannelRepository(session)
    return await repo.list_active()


async def update_channel(
    session: AsyncSession,
    id: uuid.UUID,
    data: dict[str, Any],
) -> Channel:
    """Update a channel. Validates channel_type if changed; checks name uniqueness."""
    repo = ChannelRepository(session)
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


async def delete_channel(session: AsyncSession, id: uuid.UUID) -> None:
    """Hard-delete a channel. Cascade handles subscriptions/deliveries."""
    repo = ChannelRepository(session)
    channel = await repo.get_by_id(id)
    if channel is None:
        raise NotFoundError("Channel", str(id))
    deleted = await repo.delete(id)
    if not deleted:
        raise NotFoundError("Channel", str(id))


async def test_channel(session: AsyncSession, id: uuid.UUID) -> dict:
    """Load channel, instantiate its class, call send_test(), and return the result.

    If the channel class is not yet implemented the service returns a descriptive
    error result rather than raising so callers can surface the message to the user.
    """
    channel = await get_channel(session, id)
    cls = _load_channel_class(channel.channel_type)
    if cls is None:
        return {
            "success": False,
            "error": (
                f"Channel type '{channel.channel_type}' is not implemented yet. "
                "No test could be performed."
            ),
        }
    try:
        instance = cls(channel.config)
        result = await instance.send_test()
        if result.success:
            return {"success": True, "message": "Test message sent successfully."}
        return {"success": False, "message": result.error or "Send failed with no error detail."}
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "message": str(exc)}


async def check_channel_health(session: AsyncSession, id: uuid.UUID) -> dict:
    """Run a health check and persist the result. Returns health status dict."""
    repo = ChannelRepository(session)
    channel = await get_channel(session, id)
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

    return {
        "channel_id": str(id),
        "healthy": ok,
        "error": error,
    }
