"""
Exchange order formatter.

Converts a :class:`~app.types.signal.SignalData` into a minimal order
specification dict that :class:`~app.channels.exchange.ExchangeChannel`
consumes to place a trade on a crypto exchange.

Output shape::

    {
        "symbol":       "ETH/USDT",   # direct ccxt symbol from signal.asset
        "side":         "buy",         # "buy" | "sell"
        "trade_type":   "spot",        # "spot" | "futures" | "options"
        "signal_value": 7,             # passed through for channel-level gating
        "confidence":   0.85,          # passed through for position sizing
    }

Position sizing and order_type are read from the channel config (per-account
settings), not from the signal, so they are not included here.
"""
from __future__ import annotations

from typing import Any

from app.formatters.base import AbstractFormatter
from app.formatters.registry import FormatterRegistry
from app.types.signal import SignalData

# Directions that map to a buy (long) order
_BUY_DIRECTIONS: frozenset[str] = frozenset({"call", "long"})


@FormatterRegistry.register("exchange")
class ExchangeFormatter(AbstractFormatter):
    """Formats a typed signal payload into an exchange order specification."""

    def format_signal(self, signal_data: SignalData) -> dict[str, Any]:
        direction = (signal_data.direction or "").lower()
        side = "buy" if direction in _BUY_DIRECTIONS else "sell"
        return {
            "symbol": signal_data.asset,
            "side": side,
            "trade_type": signal_data.trade_type,
            "signal_value": signal_data.signal_value,
            "confidence": signal_data.confidence,
        }

    def format_neutral(self, data: dict[str, Any]) -> dict[str, Any]:
        # No order placed for neutral signals
        return {}

    def format_outcome(self, data: dict[str, Any]) -> dict[str, Any]:
        # Outcome notifications don't place orders
        return {}

    def format_test(self) -> dict[str, Any]:
        return {
            "symbol": "BTC/USDT",
            "side": "buy",
            "trade_type": "spot",
            "_test": True,
        }
