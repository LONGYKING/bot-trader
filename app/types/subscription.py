"""Typed model for Subscription JSONB field: preferences."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class QuietHours(BaseModel):
    """Time window during which signal delivery is suppressed."""

    model_config = ConfigDict(extra="ignore")

    start: str = "22:00"
    """Start of the quiet period in ``HH:MM`` format (local time)."""

    end: str = "08:00"
    """End of the quiet period in ``HH:MM`` format (local time).
    If ``end`` < ``start`` the window spans midnight."""

    timezone: str = "UTC"
    """IANA timezone name (e.g. ``America/New_York``)."""

    @field_validator("start", "end")
    @classmethod
    def _validate_hhmm(cls, v: str) -> str:
        parts = v.split(":")
        if len(parts) != 2 or not all(p.isdigit() for p in parts):  # noqa: WPS221
            raise ValueError(f"Time must be in HH:MM format, got '{v}'")
        h, m = int(parts[0]), int(parts[1])
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError(f"Invalid time '{v}'")
        return v


class SubscriptionPreferences(BaseModel):
    """Per-subscription delivery preferences stored in ``subscriptions.preferences``.

    All fields are optional and default to unrestricted delivery.
    """

    model_config = ConfigDict(extra="ignore")

    quiet_hours: QuietHours | None = None
    """Suppress delivery during a configured local time window."""

    max_signals_per_hour: int | None = Field(None, ge=1)
    """Maximum number of signals delivered per UTC hour.  Tracked via Redis."""

    delivery_delay_seconds: int = Field(0, ge=0)
    """Defer delivery by this many seconds (e.g. to give live traders a head
    start before paper-trading subscribers receive the same signal)."""
