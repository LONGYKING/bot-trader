from app.formatters.base import AbstractFormatter
from app.formatters.registry import FormatterRegistry
from app.types.signal import SignalData

_SIGNAL_MAP: dict[int, tuple[str, str]] = {
    7: ("🚀", "STRONG BUY"),
    3: ("📈", "BUY"),
    -3: ("📉", "SELL"),
    -7: ("🔻", "STRONG SELL"),
    0: ("⏸", "NEUTRAL"),
}

_DIVIDER = "─────────────────"


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


@FormatterRegistry.register("whatsapp")
class WhatsAppFormatter(AbstractFormatter):
    def format_signal(self, signal_data: SignalData) -> str:
        signal_value = signal_data.signal_value
        asset = signal_data.asset
        direction = signal_data.direction
        tenor_days = signal_data.tenor_days
        confidence = signal_data.confidence
        regime = signal_data.regime
        entry_price = signal_data.entry_price
        rule_triggered = signal_data.rule_triggered
        indicator_snapshot = signal_data.indicator_snapshot or None
        strategy_name: str | None = None

        emoji, label = _SIGNAL_MAP.get(signal_value, ("⏸", "NEUTRAL"))

        lines: list[str] = [
            f"{emoji} *{label}* — {asset}",
            _DIVIDER,
        ]

        if strategy_name is not None:
            lines.append(f"📋 Strategy: {strategy_name}")

        if direction is not None or tenor_days is not None:
            dir_str = direction or "—"
            tenor_str = f"{tenor_days} days" if tenor_days is not None else "—"
            lines.append(f"📊 Direction: {dir_str} | Tenor: {tenor_str}")

        if entry_price is not None:
            lines.append(f"💰 Entry Price: ${entry_price:,.2f}")

        if confidence is not None:
            lines.append(f"🎯 Confidence: {confidence * 100:.1f}%")

        if regime is not None:
            lines.append(f"📈 Regime: {_format_regime(regime)}")

        if rule_triggered is not None:
            lines.append(f"🔍 Trigger: {rule_triggered}")

        if indicator_snapshot:
            lines.append(f"📉 Indicators: {_format_indicators(indicator_snapshot)}")

        lines.append(_DIVIDER)

        if tenor_days is not None:
            lines.append(f"⏱ Expires in {tenor_days} days")

        return "\n".join(lines)
