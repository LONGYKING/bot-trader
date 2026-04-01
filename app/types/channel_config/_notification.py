"""Typed config models for notification channel types."""
from __future__ import annotations

from pydantic import Field

from app.types.channel_config._base import NotificationChannelConfig


class TelegramChannelConfig(NotificationChannelConfig):
    """Config for :class:`~app.channels.telegram.TelegramChannel`."""

    bot_token: str
    """Telegram Bot API token (from @BotFather)."""

    chat_id: str
    """Target chat / channel / group ID (may be negative for groups)."""


class SlackChannelConfig(NotificationChannelConfig):
    """Config for :class:`~app.channels.slack.SlackChannel`.

    Supply either ``webhook_url`` (simpler) or ``bot_token`` + ``channel_id``.
    ``webhook_url`` takes priority if both are provided.
    """

    webhook_url: str | None = None
    bot_token: str | None = None
    channel_id: str | None = None


class DiscordChannelConfig(NotificationChannelConfig):
    """Config for :class:`~app.channels.discord.DiscordChannel`."""

    webhook_url: str
    """Discord Webhook URL."""


class WebhookChannelConfig(NotificationChannelConfig):
    """Config for :class:`~app.channels.webhook.WebhookChannel`."""

    url: str
    """Target URL that will receive POST requests."""

    secret: str | None = None
    """If set, an HMAC-SHA256 signature is added as ``X-Signature-SHA256``."""

    headers: dict[str, str] = Field(default_factory=dict)
    """Extra HTTP headers included in every request."""


class WhatsAppChannelConfig(NotificationChannelConfig):
    """Config for :class:`~app.channels.whatsapp.WhatsAppChannel` (Twilio)."""

    account_sid: str
    auth_token: str
    from_number: str
    """Twilio WhatsApp sender number in ``whatsapp:+1...`` format."""

    to_number: str
    """Recipient number in ``whatsapp:+1...`` format."""


class EmailChannelConfig(NotificationChannelConfig):
    """Config for :class:`~app.channels.email.EmailChannel`."""

    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    username: str
    password: str
    from_address: str
    to_addresses: list[str]
    """One or more recipient email addresses."""

    use_tls: bool = True
