"""
Exchange order formatter.

Converts a signal_data dict into a minimal order specification dict that
ExchangeChannel.send() consumes to place a trade on a crypto exchange.

Output shape:
    {
        "symbol":     "ETH/USDT",   # direct ccxt symbol from signal.asset
        "side":       "buy",         # "buy" | "sell"
        "trade_type": "spot",        # "spot" | "futures" | "options"
    }

Position sizing and order_type are read from the channel config (per-account
settings), not from the signal, so they are not included here.
"""
from __future__ import annotations

from typing import Any

from app.formatters.base import AbstractFormatter

# Directions that map to a buy (long) order
_BUY_DIRECTIONS = {"call", "long"}


class ExchangeFormatter(AbstractFormatter):
    """Formats signal data into an exchange order specification."""

    def format_signal(self, signal_data: dict) -> dict[str, Any]:
        direction = (signal_data.get("direction") or "").lower()
        side = "buy" if direction in _BUY_DIRECTIONS else "sell"
        return {
            "symbol": signal_data["asset"],
            "side": side,
            "trade_type": signal_data.get("trade_type", "spot"),
        }

    def format_neutral(self, data: dict) -> dict[str, Any]:
        # No order placed for neutral signals
        return {}

    def format_outcome(self, data: dict) -> dict[str, Any]:
        # Outcome notifications don't place orders
        return {}

    def format_test(self) -> dict[str, Any]:
        return {
            "symbol": "BTC/USDT",
            "side": "buy",
            "trade_type": "spot",
            "_test": True,
        }
