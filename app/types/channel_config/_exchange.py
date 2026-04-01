"""Typed config model for the exchange (execution) channel type."""
from __future__ import annotations

from pydantic import Field, field_validator

from app.types.channel_config._base import TakeProfitLevel, TradingHours, _BaseChannelConfig


class ExchangeChannelConfig(_BaseChannelConfig):
    """Complete execution config for :class:`~app.channels.exchange.ExchangeChannel`.

    Every optional field falls back to a sensible default.  Required fields
    (``exchange_id``, ``api_key``, ``api_secret``) raise ``ValidationError``
    immediately if absent.
    """

    # --- Credentials ---
    exchange_id: str
    """ccxt exchange identifier, e.g. ``"binance"``, ``"bybit"``, ``"deribit"``."""

    api_key: str
    api_secret: str
    passphrase: str | None = None
    """Required by OKX and some others."""

    testnet: bool = False
    """Connect to the exchange sandbox / paper-trading endpoint."""

    quote_currency: str | None = None
    """Override automatic margin-currency detection (e.g. ``"ETH"`` for
    Deribit inverse contracts)."""

    # --- Position sizing ---
    position_size_pct: float = Field(0.05, ge=0.0, le=1.0)
    """Fraction of free margin balance to allocate per trade."""

    position_size_fixed: float | None = Field(None, gt=0.0)
    """Fixed amount in base units.  Overrides ``position_size_pct`` when set."""

    max_position_size_pct: float | None = Field(None, gt=0.0, le=1.0)
    """Hard cap on trade size as a fraction of free balance."""

    max_position_size_fixed: float | None = Field(None, gt=0.0)
    """Hard cap in absolute base units."""

    confidence_scaling: bool = False
    """Multiply computed size by signal confidence (0–1).  A 70 % confident
    signal with ``position_size_pct=0.05`` results in a 3.5 % allocation."""

    # --- Stop loss ---
    stop_loss_pct: float | None = Field(None, gt=0.0, le=1.0)
    """Stop-loss distance from entry as a fraction of entry price (e.g. 0.03 = 3 %)."""

    stop_loss_fixed: float | None = Field(None, gt=0.0)
    """Stop-loss as a fixed loss amount in the margin currency."""

    trailing_stop_pct: float | None = Field(None, gt=0.0, le=1.0)
    """Trailing stop distance as a fraction of entry price."""

    breakeven_trigger_pct: float | None = Field(None, gt=0.0, le=1.0)
    """Move stop to entry once price moves this fraction in your favour."""

    # --- Take profit ---
    take_profit_pct: float | None = Field(None, gt=0.0)
    """Single TP target as a fraction of entry price (e.g. 0.06 = 6 %)."""

    take_profit_fixed: float | None = Field(None, gt=0.0)
    """Single TP target as a fixed profit amount in the margin currency."""

    take_profit_levels: list[TakeProfitLevel] | None = None
    """Staged take-profit exits.  Takes priority over ``take_profit_pct``/``_fixed``
    when set.  Example: ``[{"pct": 0.03, "close_ratio": 0.5}, {"pct": 0.06, "close_ratio": 0.5}]``"""

    # --- Trade gating ---
    trading_enabled: bool = True
    """Master kill-switch.  ``False`` = channel remains subscribed but places NO orders."""

    dry_run: bool = False
    """Log the intended order and return success without placing it on the exchange.
    Distinct from ``testnet`` — no exchange call is made at all."""

    direction_filter: str = "both"
    """``"long_only"`` | ``"short_only"`` | ``"both"``."""

    signal_strength_filter: list[int] | None = None
    """Only execute signals whose ``signal_value`` is in this list
    (e.g. ``[7, -7]`` to skip weak ±3 signals)."""

    trading_hours: TradingHours | None = None
    """Restrict order placement to a configured time window."""

    trading_days: list[str] | None = None
    """Restrict order placement to specific days.
    Day names: ``"mon"``, ``"tue"``, ``"wed"``, ``"thu"``, ``"fri"``, ``"sat"``, ``"sun"``."""

    # --- Exposure limits ---
    max_total_exposure_pct: float | None = Field(None, gt=0.0, le=1.0)
    """Maximum sum of all open position notionals as a fraction of account balance."""

    max_exposure_per_asset_pct: float | None = Field(None, gt=0.0, le=1.0)
    """Maximum exposure to a single asset as a fraction of account balance."""

    max_exposure_per_direction_pct: float | None = Field(None, gt=0.0, le=1.0)
    """Maximum net long-only or net short-only exposure as a fraction of account balance."""

    # --- Order execution ---
    order_type: str = "market"
    """``"market"`` or ``"limit"``."""

    limit_order_offset_pct: float = Field(0.001, ge=0.0, le=0.1)
    """For limit orders: place this fraction inside the best bid/ask to improve fill."""

    order_timeout_seconds: int = Field(30, ge=1)
    """Log a warning for unfilled limit orders after this many seconds."""

    slippage_tolerance_pct: float | None = Field(None, gt=0.0, le=1.0)
    """Reject order placement if the bid-ask spread exceeds this fraction of price."""

    leverage: int = Field(1, ge=1, le=200)
    """Futures leverage multiplier.  Only applied when ``trade_type == "futures"``."""

    # --- Position management ---
    close_on_opposite_signal: bool = True
    """Close an existing position before opening one in the opposite direction."""

    max_open_positions: int = Field(1, ge=1)
    """Maximum number of concurrent open positions per symbol."""

    @field_validator("direction_filter")
    @classmethod
    def _validate_direction_filter(cls, v: str) -> str:
        allowed = {"long_only", "short_only", "both"}
        if v not in allowed:
            raise ValueError(f"direction_filter must be one of {allowed}")
        return v

    @field_validator("order_type")
    @classmethod
    def _validate_order_type(cls, v: str) -> str:
        allowed = {"market", "limit"}
        if v not in allowed:
            raise ValueError(f"order_type must be one of {allowed}")
        return v
