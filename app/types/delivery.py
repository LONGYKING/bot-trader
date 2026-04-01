"""Typed model for SignalDelivery JSONB field: delivery_metadata."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class DeliveryMetadata(BaseModel):
    """Operational metadata recorded on every successful signal delivery.

    Stored as JSONB in ``signal_deliveries.delivery_metadata`` so it can be
    queried for latency reporting and debugging without schema changes.
    """

    model_config = ConfigDict(extra="ignore")

    latency_ms: int = Field(..., ge=0)
    """Wall-clock time from formatter call to successful ``send()`` return, in milliseconds."""

    channel_type: str
    """The channel type that received this delivery (e.g. ``telegram``, ``exchange``)."""

    formatter: str
    """Class name of the formatter used (e.g. ``TelegramFormatter``)."""

    attempt: int = Field(1, ge=1)
    """Delivery attempt number (1 = first attempt, >1 = retry)."""
