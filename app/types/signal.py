"""Typed representation of a signal payload passed between services and formatters."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

#: All valid non-neutral signal strength values.
VALID_SIGNAL_VALUES: frozenset[int] = frozenset({-7, -3, 3, 7})


class SignalData(BaseModel):
    """Structured signal payload.

    Constructed from a persisted :class:`~app.models.signal.Signal` record and
    passed to every :class:`~app.formatters.base.AbstractFormatter`.  Workers
    build this at the delivery boundary so that missing or mistyped fields fail
    early with a clear validation error rather than silently returning ``None``
    inside a formatter.
    """

    model_config = ConfigDict(extra="ignore")

    asset: str
    signal_value: int
    trade_type: str = "options"
    direction: str | None = None
    tenor_days: int | None = None
    confidence: float | None = None
    regime: str | None = None
    entry_price: float | None = None
    rule_triggered: str | None = None
    indicator_snapshot: dict[str, float | int | bool | str] = Field(default_factory=dict)
