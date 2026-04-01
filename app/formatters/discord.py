from datetime import UTC, datetime
from typing import Any

from app.formatters.base import AbstractFormatter
from app.types.signal import SignalData

_SIGNAL_MAP: dict[int, tuple[str, str]] = {
    7: ("🚀", "STRONG BUY"),
    3: ("📈", "BUY"),
    -3: ("📉", "SELL"),
    -7: ("🔻", "STRONG SELL"),
    0: ("⏸", "NEUTRAL"),
}

# Discord embed colour codes
_COLOR_BUY = 0x00FF00   # green
_COLOR_SELL = 0xFF0000  # red
_COLOR_NEUTRAL = 0xAAAAAA  # grey


def _get_color(signal_value: int) -> int:
    if signal_value > 0:
        return _COLOR_BUY
    if signal_value < 0:
        return _COLOR_SELL
    return _COLOR_NEUTRAL


def _format_regime(regime: str) -> str:
    return regime.replace("_", " ").title()


def _format_indicators(snapshot: dict) -> str:
    parts: list[str] = []
    for key, value in snapshot.items():
        label = key.replace("_", " ").upper()
        if isinstance(value, float):
            parts.append(f"{label}: {value:g}")
        else:
            parts.append(f"{label}: {value}")
    return " | ".join(parts)


class DiscordFormatter(AbstractFormatter):
    def format_signal(self, signal_data: SignalData) -> dict[str, Any]:
        signal_value = signal_data.signal_value
        asset = signal_data.asset
        direction = signal_data.direction
        tenor_days = signal_data.tenor_days
        confidence = signal_data.confidence
        regime = signal_data.regime
        entry_price = signal_data.entry_price
        rule_triggered = signal_data.rule_triggered
        indicator_snapshot = signal_data.indicator_snapshot or None
        strategy_name: str | None = None  # not in SignalData; passed via format_neutral if needed

        emoji, label = _SIGNAL_MAP.get(signal_value, ("⏸", "NEUTRAL"))
        color = _get_color(signal_value)

        fields: list[dict] = []

        if direction is not None:
            fields.append(
                {"name": "Direction", "value": direction, "inline": True}
            )

        if tenor_days is not None:
            fields.append(
                {"name": "Tenor", "value": f"{tenor_days} days", "inline": True}
            )

        if entry_price is not None:
            fields.append(
                {
                    "name": "Entry Price",
                    "value": f"${entry_price:,.2f}",
                    "inline": True,
                }
            )

        if confidence is not None:
            fields.append(
                {
                    "name": "Confidence",
                    "value": f"{confidence * 100:.1f}%",
                    "inline": True,
                }
            )

        if regime is not None:
            fields.append(
                {
                    "name": "Regime",
                    "value": _format_regime(regime),
                    "inline": True,
                }
            )

        if tenor_days is not None:
            fields.append(
                {
                    "name": "Expires In",
                    "value": f"{tenor_days} days",
                    "inline": True,
                }
            )

        if rule_triggered is not None:
            fields.append(
                {"name": "Trigger", "value": rule_triggered, "inline": False}
            )

        if indicator_snapshot:
            fields.append(
                {
                    "name": "Indicators",
                    "value": _format_indicators(indicator_snapshot),
                    "inline": False,
                }
            )

        if strategy_name is not None:
            fields.append(
                {"name": "Strategy", "value": strategy_name, "inline": True}
            )

        embed: dict[str, Any] = {
            "title": f"{emoji} {label} — {asset}",
            "color": color,
            "fields": fields,
            "timestamp": datetime.now(tz=UTC).isoformat(),
        }

        return {"embeds": [embed]}
