import random

from app.formatters.base import AbstractFormatter

# Maps signal_value → (emoji, label)
_SCAN_LINES = [
    "Combing through the candles...",
    "Watching the tape closely...",
    "Markets are breathing. Waiting for the right moment.",
    "Indicators are loaded. No trigger yet.",
    "Price action is consolidating. Standing by.",
    "RSI and MACD checked. No edge right now.",
    "Patience is a position.",
    "Still scanning. The setup isn't there yet.",
]

_WIN_LINES = [
    "Another one in the bag. 💼",
    "The algo delivered. 🎯",
    "Precision entry, clean exit. That's the system working.",
    "Rules followed → profit captured. Repeat.",
    "Trade closed in profit. The edge compounds.",
]

_LOSS_LINES = [
    "Premium spent, lesson banked. Onward.",
    "Not every trade wins — that's what position sizing is for.",
    "Small loss, controlled risk. The system stays intact.",
    "The market said no. We move to the next setup.",
    "Stop respected. Capital protected. Next signal incoming.",
]

_SIGNAL_MAP: dict[int, tuple[str, str]] = {
    7: ("🚀", "STRONG BUY"),
    3: ("📈", "BUY"),
    -3: ("📉", "SELL"),
    -7: ("🔻", "STRONG SELL"),
    0: ("⏸", "NEUTRAL"),
}

_DIVIDER = "━━━━━━━━━━━━━━━━"


def _format_regime(regime: str) -> str:
    """Convert snake_case regime to Title Case."""
    return regime.replace("_", " ").title()


def _format_indicators(snapshot: dict) -> str:
    """Render indicator snapshot as 'Key: Value | Key: Value' string."""
    parts: list[str] = []
    for key, value in snapshot.items():
        label = key.replace("_", " ").upper()
        if isinstance(value, float):
            parts.append(f"{label}: {value:g}")
        else:
            parts.append(f"{label}: {value}")
    return " | ".join(parts)


class TelegramFormatter(AbstractFormatter):
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

        emoji, label = _SIGNAL_MAP.get(signal_value, ("⏸", "NEUTRAL"))

        lines: list[str] = [
            f"{emoji} <b>{label} — {asset}</b>",
            _DIVIDER,
        ]

        # Direction + tenor line
        if direction is not None or tenor_days is not None:
            dir_str = direction or "—"
            tenor_str = f"{tenor_days} days" if tenor_days is not None else "—"
            lines.append(f"📊 <b>Direction:</b> {dir_str} | Tenor: {tenor_str}")

        if entry_price is not None:
            lines.append(f"💰 <b>Entry Price:</b> ${entry_price:,.2f}")

        if confidence is not None:
            lines.append(f"🎯 <b>Confidence:</b> {confidence * 100:.1f}%")

        if regime is not None:
            lines.append(f"📈 <b>Regime:</b> {_format_regime(regime)}")

        if rule_triggered is not None:
            # Strip "Test signal — " prefix for cleaner display when it appears
            display_rule = rule_triggered
            if display_rule.startswith("Test signal — "):
                display_rule = display_rule[len("Test signal — "):]
            lines.append(f"🔍 <b>Trigger:</b> {display_rule}")

        if indicator_snapshot:
            lines.append(f"📉 <b>Indicators:</b> {_format_indicators(indicator_snapshot)}")

        lines.append(_DIVIDER)

        if tenor_days is not None:
            lines.append(f"⏱ Expires in {tenor_days} days")

        return "\n".join(lines)

    def format_neutral(self, data: dict) -> str:
        asset: str = data.get("asset", "UNKNOWN")
        timeframe: str = data.get("timeframe", "")
        price: float | None = data.get("current_price")
        regime: str | None = data.get("regime")
        snapshot: dict = data.get("indicator_snapshot") or {}
        strategy_name: str | None = data.get("strategy_name")

        lines: list[str] = [
            f"🔍 <b>Market Scan — {asset}</b>",
            _DIVIDER,
            f"📡 <i>{random.choice(_SCAN_LINES)}</i>",
            "",
        ]

        if price is not None:
            lines.append(f"💵 <b>Price:</b> ${price:,.2f}")
        if timeframe:
            lines.append(f"🕐 <b>Timeframe:</b> {timeframe}")
        if regime:
            lines.append(f"🌊 <b>Regime:</b> {_format_regime(regime)}")
        if snapshot:
            lines.append(f"📊 <b>Indicators:</b> {_format_indicators(snapshot)}")
        if strategy_name:
            lines.append(f"⚙️ <b>Strategy:</b> {strategy_name}")

        lines += [
            "",
            _DIVIDER,
            "⏰ <i>No signal this cycle — next scan in ~15 min</i>",
        ]
        return "\n".join(lines)

    def format_outcome(self, data: dict) -> str:
        asset: str = data.get("asset", "UNKNOWN")
        direction: str = (data.get("direction") or "").upper()
        tenor_days: int | None = data.get("tenor_days")
        entry_price: float | None = data.get("entry_price")
        exit_price: float | None = data.get("exit_price")
        pnl_pct: float = float(data.get("pnl_pct", 0))
        is_profitable: bool = bool(data.get("is_profitable", pnl_pct > 0))
        entry_time: str | None = data.get("entry_time")
        exit_time: str | None = data.get("exit_time")

        if is_profitable:
            header = f"🏆 <b>TRADE CLOSED — {asset} [WIN]</b>"
            result_icon = "✅"
            flavour = random.choice(_WIN_LINES)
        else:
            header = f"📉 <b>TRADE CLOSED — {asset} [LOSS]</b>"
            result_icon = "❌"
            flavour = random.choice(_LOSS_LINES)

        lines: list[str] = [header, _DIVIDER]

        tenor_str = f"{tenor_days}-day tenor" if tenor_days else ""
        if direction and tenor_str:
            lines.append(f"📊 <b>{direction}</b> | {tenor_str}")
        elif direction:
            lines.append(f"📊 <b>{direction}</b>")

        if entry_price is not None and exit_price is not None:
            lines.append(f"💰 Entry: <b>${entry_price:,.2f}</b>  →  Exit: <b>${exit_price:,.2f}</b>")

        lines.append(f"{result_icon} <b>PnL: {pnl_pct:+.2f}%</b>")
        lines.append("")
        lines.append(f"<i>{flavour}</i>")

        if entry_time or exit_time:
            lines.append(_DIVIDER)
            if entry_time:
                lines.append(f"🕐 Opened: {str(entry_time)[:16]}")
            if exit_time:
                lines.append(f"🕑 Closed: {str(exit_time)[:16]}")

        return "\n".join(lines)
