"""Typed config models for every channel type.

Channel credentials are encrypted at rest in the ``channels.config`` JSONB
column, so they are stored and retrieved as a plain ``dict``.  Each channel
implementation calls ``<Config>.model_validate(self.config)`` in its
constructor to validate and coerce the decrypted dict before use.  Any
missing required field or wrong type raises a ``ValidationError`` at the
first send rather than silently doing the wrong thing mid-execution.

Hierarchy:
    _BaseChannelConfig          — shared infra keys (circuit breaker, retries, rate limiting)
    ├── NotificationChannelConfig   — shared notification-filter keys (Telegram, Slack, Discord…)
    │   ├── TelegramChannelConfig
    │   ├── SlackChannelConfig
    │   ├── DiscordChannelConfig
    │   ├── WebhookChannelConfig
    │   ├── WhatsAppChannelConfig
    │   └── EmailChannelConfig
    └── ExchangeChannelConfig    — full execution config
"""
from app.types.channel_config._base import (
    NotificationChannelConfig,
    TakeProfitLevel,
    TradingHours,
    _BaseChannelConfig,
)
from app.types.channel_config._exchange import ExchangeChannelConfig
from app.types.channel_config._notification import (
    DiscordChannelConfig,
    EmailChannelConfig,
    SlackChannelConfig,
    TelegramChannelConfig,
    WebhookChannelConfig,
    WhatsAppChannelConfig,
)

_NOTIFICATION_CONFIG_MAP: dict[str, type[NotificationChannelConfig]] = {
    "telegram": TelegramChannelConfig,
    "slack": SlackChannelConfig,
    "discord": DiscordChannelConfig,
    "webhook": WebhookChannelConfig,
    "whatsapp": WhatsAppChannelConfig,
    "email": EmailChannelConfig,
}


def parse_channel_config(
    channel_type: str, raw: dict
) -> ExchangeChannelConfig | NotificationChannelConfig | _BaseChannelConfig:
    """Parse a raw decrypted config dict into the appropriate typed config model.

    Falls back to ``_BaseChannelConfig`` for unknown channel types so that
    shared infrastructure keys (CB overrides, retry policy, rate limiting)
    are always available.
    """
    if channel_type == "exchange":
        return ExchangeChannelConfig.model_validate(raw)
    model_cls = _NOTIFICATION_CONFIG_MAP.get(channel_type)
    if model_cls is not None:
        return model_cls.model_validate(raw)
    return _BaseChannelConfig.model_validate(raw)


__all__ = [
    "_BaseChannelConfig",
    "NotificationChannelConfig",
    "TakeProfitLevel",
    "TradingHours",
    "TelegramChannelConfig",
    "SlackChannelConfig",
    "DiscordChannelConfig",
    "WebhookChannelConfig",
    "WhatsAppChannelConfig",
    "EmailChannelConfig",
    "ExchangeChannelConfig",
    "parse_channel_config",
]
