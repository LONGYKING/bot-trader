from app.formatters.base import AbstractFormatter

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


class WhatsAppFormatter(AbstractFormatter):
    def format_signal(self, signal_data: dict) -> str:
        signal_value: int = signal_data.get("signal_value", 0)
        asset: str = signal_data.get("asset", "UNKNOWN")
        direction: str | None = signal_data.get("direction")
        tenor_days: int | None = signal_data.get("tenor_days")
        confidence: float | None = signal_data.get("confidence")
        regime: str | None = signal_data.get("regime")
        entry_price: float | None = signal_data.get("entry_price")
        rule_triggered: str | None = signal_data.get("rule_triggered")
        indicator_snapshot: dict | None = signal_data.get("indicator_snapshot")
        strategy_name: str | None = signal_data.get("strategy_name")

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
