"""Typed models for Strategy JSONB fields: risk_config and execution_params."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class StrategyRiskConfig(BaseModel):
    """Per-strategy risk gates stored in ``strategies.risk_config``.

    All fields are optional — absent keys use the default.  Extra keys in the
    stored JSON are silently ignored so that older config rows remain valid
    after new fields are added.
    """

    model_config = ConfigDict(extra="ignore")

    min_confidence_threshold: float | None = None
    """Reject signals whose confidence is below this value (0–1)."""

    max_daily_signals: int | None = None
    """Hard cap on signals fired per UTC day.  Tracked via Redis."""

    cooldown_minutes: int | None = Field(None, gt=0)
    """Minimum gap in minutes between consecutive signals.  Tracked via Redis."""

    suppress_duplicate_signals: bool = False
    """If ``True``, suppress a new signal when an open position in the same
    direction already exists on the exchange channel."""


class OptionsExecutionParams(BaseModel):
    """Execution parameters for options-type strategies."""

    model_config = ConfigDict(extra="ignore")

    premium_pct: float = Field(0.025, ge=0.0, le=1.0)
    """Target premium as a fraction of notional (e.g. 0.025 = 2.5 %)."""

    profit_cap_pct: float = Field(0.10, ge=0.0, le=10.0)
    """Close position once unrealised PnL exceeds this fraction of notional."""

    tenor_days_weak: int = Field(3, ge=1)
    """Expiry window in days for weak signals (±3)."""

    tenor_days_strong: int = Field(7, ge=1)
    """Expiry window in days for strong signals (±7)."""


class SpotExecutionParams(BaseModel):
    """Execution parameters for spot/futures-type strategies."""

    model_config = ConfigDict(extra="ignore")

    position_size_pct: float = Field(0.10, ge=0.0, le=1.0)
    """Fraction of free balance to allocate per trade."""

    stop_loss_pct: float = Field(0.05, ge=0.0, le=1.0)
    """Stop-loss distance from entry as a fraction of entry price."""

    take_profit_pct: float = Field(0.15, ge=0.0, le=10.0)
    """Take-profit distance from entry as a fraction of entry price."""

    max_open_positions: int = Field(20, ge=1)
    """Maximum number of concurrent open positions."""
