from typing import Any

from app.formatters.base import AbstractFormatter

_SIGNAL_MAP: dict[int, tuple[str, str]] = {
    7: ("🚀", "STRONG BUY"),
    3: ("📈", "BUY"),
    -3: ("📉", "SELL"),
    -7: ("🔻", "STRONG SELL"),
    0: ("⏸", "NEUTRAL"),
}


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


class SlackFormatter(AbstractFormatter):
    def format_signal(self, signal_data: dict) -> dict[str, Any]:
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

        blocks: list[dict] = []

        # Header block
        blocks.append(
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} {label} — {asset}",
                    "emoji": True,
                },
            }
        )

        blocks.append({"type": "divider"})

        # Build detail fields
        fields: list[dict] = []

        if direction is not None or tenor_days is not None:
            dir_str = direction or "—"
            tenor_str = f"{tenor_days} days" if tenor_days is not None else "—"
            fields.append(
                {
                    "type": "mrkdwn",
                    "text": f"*Direction*\n{dir_str}",
                }
            )
            fields.append(
                {
                    "type": "mrkdwn",
                    "text": f"*Tenor*\n{tenor_str}",
                }
            )

        if entry_price is not None:
            fields.append(
                {
                    "type": "mrkdwn",
                    "text": f"*Entry Price*\n${entry_price:,.2f}",
                }
            )

        if confidence is not None:
            fields.append(
                {
                    "type": "mrkdwn",
                    "text": f"*Confidence*\n{confidence * 100:.1f}%",
                }
            )

        if regime is not None:
            fields.append(
                {
                    "type": "mrkdwn",
                    "text": f"*Regime*\n{_format_regime(regime)}",
                }
            )

        if tenor_days is not None:
            fields.append(
                {
                    "type": "mrkdwn",
                    "text": f"*Expires In*\n{tenor_days} days",
                }
            )

        # Slack section blocks accept at most 10 fields; split if needed
        for i in range(0, len(fields), 10):
            blocks.append(
                {
                    "type": "section",
                    "fields": fields[i : i + 10],
                }
            )

        if rule_triggered is not None:
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Trigger*\n{rule_triggered}",
                    },
                }
            )

        if indicator_snapshot:
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Indicators*\n{_format_indicators(indicator_snapshot)}",
                    },
                }
            )

        blocks.append({"type": "divider"})

        return {"blocks": blocks}
