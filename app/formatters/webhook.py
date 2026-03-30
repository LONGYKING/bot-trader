from datetime import datetime, timezone
from typing import Any

from app.formatters.base import AbstractFormatter


class WebhookFormatter(AbstractFormatter):
    def format_signal(self, signal_data: dict) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "version": "1.0",
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        }

        # Include all known signal fields if present
        for field in (
            "asset",
            "signal_value",
            "direction",
            "tenor_days",
            "confidence",
            "regime",
            "entry_price",
            "rule_triggered",
            "indicator_snapshot",
            "strategy_name",
        ):
            value = signal_data.get(field)
            if value is not None:
                payload[field] = value

        return payload
