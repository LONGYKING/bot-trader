"""
Domain type models for bot-trader.

All structured JSONB fields that were previously raw ``dict`` now have
a Pydantic model defined here. Workers and services parse incoming data
through these models at the boundary so that type errors surface
immediately rather than silently mid-execution.

Usage::

    from app.types.signal import SignalData
    from app.types.channel_config import ExchangeChannelConfig
    from app.types.subscription import SubscriptionPreferences
    from app.types.strategy import StrategyRiskConfig
    from app.types.delivery import DeliveryMetadata
"""
