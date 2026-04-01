"""
Strategy package.

Importing this package triggers registration of all built-in strategies via
the ``@StrategyRegistry.register`` decorator in each module.
"""
from app.strategies import (  # noqa: F401
    adx_trend,
    bollinger_breakout,
    ema_crossover,
    macd_rsi,
    rsi_divergence,
    vwap_reversion,
)

__all__ = [
    "macd_rsi",
    "bollinger_breakout",
    "rsi_divergence",
    "ema_crossover",
    "adx_trend",
    "vwap_reversion",
]
