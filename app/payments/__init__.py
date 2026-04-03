from __future__ import annotations


def _provider_config(provider: str) -> dict:
    """Extract the config slice for a given provider from settings."""
    from app.config import get_settings

    settings = get_settings()
    configs: dict[str, dict] = {
        "stripe": {
            "secret_key": settings.stripe_secret_key,
            "webhook_secret": settings.stripe_webhook_secret,
        },
        "paddle": {
            "api_key": settings.paddle_api_key,
            "webhook_secret": settings.paddle_webhook_secret,
            "environment": settings.paddle_environment,
        },
        "lemonsqueezy": {
            "api_key": settings.lemonsqueezy_api_key,
            "webhook_secret": settings.lemonsqueezy_webhook_secret,
            "store_id": settings.lemonsqueezy_store_id,
        },
    }
    if provider not in configs:
        raise ValueError(f"No config defined for payment provider '{provider}'")
    return configs[provider]


from app.payments.registry import get_payment_adapter  # noqa: E402, F401
