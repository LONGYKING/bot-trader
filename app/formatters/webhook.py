from datetime import UTC, datetime
from typing import Any

from app.formatters.base import AbstractFormatter
from app.formatters.registry import FormatterRegistry
from app.types.signal import SignalData


@FormatterRegistry.register("webhook")
class WebhookFormatter(AbstractFormatter):
    def format_signal(self, signal_data: SignalData) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "version": "1.0",
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "asset": signal_data.asset,
            "signal_value": signal_data.signal_value,
            "trade_type": signal_data.trade_type,
        }

        # Include optional fields only when set
        optional_fields: dict[str, Any] = {
            "direction": signal_data.direction,
            "tenor_days": signal_data.tenor_days,
            "confidence": signal_data.confidence,
            "regime": signal_data.regime,
            "entry_price": signal_data.entry_price,
            "rule_triggered": signal_data.rule_triggered,
            "indicator_snapshot": signal_data.indicator_snapshot or None,
        }
        payload.update({k: v for k, v in optional_fields.items() if v is not None})

        return payload
