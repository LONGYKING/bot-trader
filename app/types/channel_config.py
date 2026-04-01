"""Typed config models for every channel type.

Channel credentials are encrypted at rest in the ``channels.config`` JSONB
column, so they are stored and retrieved as a plain ``dict``.  Each channel
implementation calls ``<Config>.model_validate(self.config)`` in its
constructor to validate and coerce the decrypted dict before use.  Any
missing required field or wrong type raises a ``ValidationError`` at the
first send rather than silently doing the wrong thing mid-execution.

Hierarchy:
    _BaseChannelConfig          — shared infra keys (circuit breaker, retries, rate limiting)
    ├── NotificationChannelConfig   — shared notification-filter keys (Telegram, Slack, Discord…)
    │   ├── TelegramChannelConfig
    │   ├── SlackChannelConfig
    │   ├── DiscordChannelConfig
    │   ├── WebhookChannelConfig
    │   ├── WhatsAppChannelConfig
    │   └── EmailChannelConfig
    └── ExchangeChannelConfig    — full execution config
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ---------------------------------------------------------------------------
# Shared sub-models
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Base configs
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Notification channel configs
# ---------------------------------------------------------------------------


class TelegramChannelConfig(NotificationChannelConfig):
    """Config for :class:`~app.channels.telegram.TelegramChannel`."""

    bot_token: str
    """Telegram Bot API token (from @BotFather)."""

    chat_id: str
    """Target chat / channel / group ID (may be negative for groups)."""


class SlackChannelConfig(NotificationChannelConfig):
    """Config for :class:`~app.channels.slack.SlackChannel`.

    Supply either ``webhook_url`` (simpler) or ``bot_token`` + ``channel_id``.
    ``webhook_url`` takes priority if both are provided.
    """

    webhook_url: str | None = None
    bot_token: str | None = None
    channel_id: str | None = None


class DiscordChannelConfig(NotificationChannelConfig):
    """Config for :class:`~app.channels.discord.DiscordChannel`."""

    webhook_url: str
    """Discord Webhook URL."""


class WebhookChannelConfig(NotificationChannelConfig):
    """Config for :class:`~app.channels.webhook.WebhookChannel`."""

    url: str
    """Target URL that will receive POST requests."""

    secret: str | None = None
    """If set, an HMAC-SHA256 signature is added as ``X-Signature-SHA256``."""

    headers: dict[str, str] = Field(default_factory=dict)
    """Extra HTTP headers included in every request."""


class WhatsAppChannelConfig(NotificationChannelConfig):
    """Config for :class:`~app.channels.whatsapp.WhatsAppChannel` (Twilio)."""

    account_sid: str
    auth_token: str
    from_number: str
    """Twilio WhatsApp sender number in ``whatsapp:+1...`` format."""

    to_number: str
    """Recipient number in ``whatsapp:+1...`` format."""


class EmailChannelConfig(NotificationChannelConfig):
    """Config for :class:`~app.channels.email.EmailChannel`."""

    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    username: str
    password: str
    from_address: str
    to_addresses: list[str]
    """One or more recipient email addresses."""

    use_tls: bool = True


# ---------------------------------------------------------------------------
# Exchange channel config
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Registry helper
# ---------------------------------------------------------------------------

_NOTIFICATION_CONFIG_MAP: dict[str, type[NotificationChannelConfig]] = {
    "telegram": TelegramChannelConfig,
    "slack": SlackChannelConfig,
    "discord": DiscordChannelConfig,
    "webhook": WebhookChannelConfig,
    "whatsapp": WhatsAppChannelConfig,
    "email": EmailChannelConfig,
}


def parse_channel_config(
    channel_type: str, raw: dict
) -> ExchangeChannelConfig | NotificationChannelConfig | _BaseChannelConfig:
    """Parse a raw decrypted config dict into the appropriate typed config model.

    Falls back to ``_BaseChannelConfig`` for unknown channel types so that
    shared infrastructure keys (CB overrides, retry policy, rate limiting)
    are always available.
    """
    if channel_type == "exchange":
        return ExchangeChannelConfig.model_validate(raw)
    model_cls = _NOTIFICATION_CONFIG_MAP.get(channel_type)
    if model_cls is not None:
        return model_cls.model_validate(raw)
    return _BaseChannelConfig.model_validate(raw)
