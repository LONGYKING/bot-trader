"""Base channel config models shared across all channel types."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TakeProfitLevel(BaseModel):
    """A single staged take-profit target."""

    model_config = ConfigDict(extra="ignore")

    pct: float = Field(..., gt=0.0)
    """Distance from entry as a fraction (e.g. 0.03 = 3 %)."""

    close_ratio: float = Field(1.0, gt=0.0, le=1.0)
    """Fraction of position to close at this level (e.g. 0.5 = 50 %)."""


class TradingHours(BaseModel):
    """Time window during which new orders are allowed."""

    model_config = ConfigDict(extra="ignore")

    start: str = "00:00"
    """Window open time in ``HH:MM`` format."""

    end: str = "23:59"
    """Window close time in ``HH:MM`` format.  If ``end`` < ``start`` the
    window spans midnight."""

    timezone: str = "UTC"
    """IANA timezone name (e.g. ``Asia/Tokyo``)."""


class _BaseChannelConfig(BaseModel):
    """Infrastructure keys shared by every channel type.

    ``extra="allow"`` is intentional: channel-specific credential keys (e.g.
    ``bot_token``) are handled by the concrete subclass, and any unknown keys
    stored in legacy config rows are forwarded without error.
    """

    model_config = ConfigDict(extra="allow")

    # --- Circuit breaker overrides (fall back to global Settings if None) ---
    cb_failure_threshold: int | None = Field(None, ge=1)
    cb_recovery_timeout: int | None = Field(None, ge=1)
    cb_window_seconds: int | None = Field(None, ge=1)

    # --- Retry policy overrides (fall back to global Settings if None) ---
    max_retries: int | None = Field(None, ge=0)
    backoff_base_seconds: int | None = Field(None, ge=1)
    backoff_max_seconds: int | None = Field(None, ge=1)

    # --- Per-channel rate limiting ---
    rate_limit_per_minute: int | None = Field(None, ge=1)
    """Maximum number of outbound messages per minute.  Enforced in the
    ``deliver_signal`` worker via a Redis sliding-window counter."""


class NotificationChannelConfig(_BaseChannelConfig):
    """Signal-filter keys shared by all *notification* channel types
    (Telegram, Slack, Discord, Webhook, WhatsApp, Email).

    These do not apply to the exchange channel.
    """

    notifications_enabled: bool = True
    """Master switch.  ``False`` pauses delivery without deactivating the channel."""

    min_signal_strength: int | None = Field(None, ge=1)
    """Only deliver signals whose ``|signal_value|`` meets or exceeds this.
    ``None`` = deliver all (including weak ±3).  Set to ``7`` for strong-only."""

    trade_type_filter: list[str] | None = None
    """Restrict delivery to these trade types (e.g. ``["futures", "spot"]``).
    ``None`` = no restriction."""

    direction_filter: str = "both"
    """``"long_only"`` | ``"short_only"`` | ``"both"``."""

    @field_validator("direction_filter")
    @classmethod
    def _validate_direction_filter(cls, v: str) -> str:
        allowed = {"long_only", "short_only", "both"}
        if v not in allowed:
            raise ValueError(f"direction_filter must be one of {allowed}")
        return v
