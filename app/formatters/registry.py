from app.formatters.base import AbstractFormatter
from app.formatters.discord import DiscordFormatter
from app.formatters.email import EmailFormatter
from app.formatters.exchange import ExchangeFormatter
from app.formatters.slack import SlackFormatter
from app.formatters.telegram import TelegramFormatter
from app.formatters.webhook import WebhookFormatter
from app.formatters.whatsapp import WhatsAppFormatter

_FORMATTERS: dict[str, type[AbstractFormatter]] = {
    "telegram": TelegramFormatter,
    "slack": SlackFormatter,
    "discord": DiscordFormatter,
    "whatsapp": WhatsAppFormatter,
    "email": EmailFormatter,
    "webhook": WebhookFormatter,
    "exchange": ExchangeFormatter,
}


def get_formatter(channel_type: str) -> AbstractFormatter:
    """Return a fresh formatter instance for the given channel type.

    Raises:
        ValueError: if ``channel_type`` has no registered formatter.
    """
    klass = _FORMATTERS.get(channel_type)
    if klass is None:
        raise ValueError(
            f"No formatter registered for channel type '{channel_type}'. "
            f"Available: {sorted(_FORMATTERS.keys())}"
        )
    return klass()


def list_formatter_types() -> list[str]:
    """Return the sorted list of channel types that have formatters."""
    return sorted(_FORMATTERS.keys())
