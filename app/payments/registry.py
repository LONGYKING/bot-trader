from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.payments.base import AbstractPaymentAdapter


class PaymentAdapterRegistry:
    """Class-based registry for payment adapters.

    Adapters self-register via ``@PaymentAdapterRegistry.register("<provider>")``
    so adding a new payment provider requires editing only one file.
    """

    _registry: dict[str, type[AbstractPaymentAdapter]] = {}

    @classmethod
    def register(cls, provider: str):
        """Decorator that registers an adapter class for a payment provider."""
        def decorator(klass: type[AbstractPaymentAdapter]) -> type[AbstractPaymentAdapter]:
            cls._registry[provider] = klass
            return klass
        return decorator

    @classmethod
    def get(cls, provider: str, config: dict[str, Any]) -> AbstractPaymentAdapter:
        klass = cls._registry.get(provider)
        if klass is None:
            raise ValueError(
                f"Unknown payment provider: '{provider}'. "
                f"Available: {sorted(cls._registry)}"
            )
        return klass(config)

    @classmethod
    def available(cls) -> list[str]:
        return sorted(cls._registry)


def get_payment_adapter(provider: str | None = None) -> AbstractPaymentAdapter:
    """Return a configured adapter instance for the given (or active) provider."""
    from app.config import get_settings
    from app.payments import _provider_config

    settings = get_settings()
    active = provider or settings.payment_provider
    return PaymentAdapterRegistry.get(active, _provider_config(active))


# Import all adapter modules to trigger @PaymentAdapterRegistry.register side-effects.
# Placed after the class definition to avoid circular imports.
import app.payments.stripe       # noqa: F401, E402
import app.payments.paddle       # noqa: F401, E402
import app.payments.lemonsqueezy  # noqa: F401, E402
