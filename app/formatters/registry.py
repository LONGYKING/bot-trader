from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.formatters.base import AbstractFormatter


class FormatterRegistry:
    """Class-based registry for signal formatters.

    Formatters self-register via ``@FormatterRegistry.register("<channel_type>")``
    so adding a new formatter requires editing only one file.
    """

    _registry: dict[str, type[AbstractFormatter]] = {}

    @classmethod
    def register(cls, channel_type: str):
        """Decorator that registers a formatter class for a channel type."""
        def decorator(klass: type[AbstractFormatter]) -> type[AbstractFormatter]:
            cls._registry[channel_type] = klass
            return klass
        return decorator

    @classmethod
    def get(cls, channel_type: str) -> type[AbstractFormatter]:
        klass = cls._registry.get(channel_type)
        if klass is None:
            raise ValueError(
                f"No formatter registered for channel type '{channel_type}'. "
                f"Available: {sorted(cls._registry)}"
            )
        return klass

    @classmethod
    def list_all(cls) -> list[str]:
        return sorted(cls._registry)


def get_formatter(channel_type: str) -> AbstractFormatter:
    """Return a fresh formatter instance for the given channel type."""
    return FormatterRegistry.get(channel_type)()


def list_formatter_types() -> list[str]:
    """Return the sorted list of channel types that have formatters."""
    return FormatterRegistry.list_all()


# Import all formatter modules to trigger @FormatterRegistry.register side-effects.
# These imports are placed after the class definition to avoid circular import
# issues — Python returns the partial module object (with FormatterRegistry already
# defined) when the formatter files import back from this module.
import app.formatters.discord  # noqa: F401, E402
import app.formatters.email  # noqa: F401, E402
import app.formatters.exchange  # noqa: F401, E402
import app.formatters.slack  # noqa: F401, E402
import app.formatters.telegram  # noqa: F401, E402
import app.formatters.webhook  # noqa: F401, E402
import app.formatters.whatsapp  # noqa: F401, E402
