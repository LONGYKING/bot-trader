from typing import Any

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

_COLOR_BUY = "#00aa55"
_COLOR_SELL = "#cc2200"
_COLOR_NEUTRAL = "#888888"
_COLOR_HEADER_BG = "#1a1a2e"
_COLOR_ROW_ALT = "#f9f9f9"


def _get_color(signal_value: int) -> str:
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


def _table_row(label: str, value: str, alt: bool = False) -> str:
    bg = _COLOR_ROW_ALT if alt else "#ffffff"
    return (
        f"<tr style='background:{bg};'>"
        f"<td style='padding:8px 12px;font-weight:bold;color:#333;width:35%;border-bottom:1px solid #e0e0e0;'>{label}</td>"
        f"<td style='padding:8px 12px;color:#444;border-bottom:1px solid #e0e0e0;'>{value}</td>"
        f"</tr>"
    )


@FormatterRegistry.register("email")
class EmailFormatter(AbstractFormatter):
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
        strategy_name: str | None = None

        emoji, label = _SIGNAL_MAP.get(signal_value, ("⏸", "NEUTRAL"))
        signal_color = _get_color(signal_value)

        # ── Subject ────────────────────────────────────────────────────────────
        subject = f"{emoji} Signal Alert: {label} {asset}"

        # ── HTML ───────────────────────────────────────────────────────────────
        rows_html: list[str] = []
        alt = False

        rows_html.append(_table_row("Asset", asset, alt))
        alt = not alt
        rows_html.append(
            _table_row(
                "Signal",
                f"<span style='color:{signal_color};font-weight:bold;'>{emoji} {label}</span>",
                alt,
            )
        )
        alt = not alt

        if strategy_name is not None:
            rows_html.append(_table_row("Strategy", strategy_name, alt))
            alt = not alt

        if direction is not None:
            rows_html.append(_table_row("Direction", direction, alt))
            alt = not alt

        if tenor_days is not None:
            rows_html.append(_table_row("Tenor", f"{tenor_days} days", alt))
            alt = not alt

        if entry_price is not None:
            rows_html.append(_table_row("Entry Price", f"${entry_price:,.2f}", alt))
            alt = not alt

        if confidence is not None:
            rows_html.append(
                _table_row("Confidence", f"{confidence * 100:.1f}%", alt)
            )
            alt = not alt

        if regime is not None:
            rows_html.append(_table_row("Regime", _format_regime(regime), alt))
            alt = not alt

        if rule_triggered is not None:
            rows_html.append(_table_row("Trigger", rule_triggered, alt))
            alt = not alt

        if indicator_snapshot:
            rows_html.append(
                _table_row("Indicators", _format_indicators(indicator_snapshot), alt)
            )
            alt = not alt

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{subject}</title>
</head>
<body style="margin:0;padding:0;font-family:Arial,sans-serif;background:#f4f4f4;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f4;padding:30px 0;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0"
               style="background:#ffffff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.1);">
          <!-- Header -->
          <tr>
            <td colspan="2"
                style="background:{_COLOR_HEADER_BG};padding:24px 20px;text-align:center;">
              <h1 style="margin:0;color:#ffffff;font-size:22px;letter-spacing:1px;">
                {emoji} {label}
              </h1>
              <p style="margin:6px 0 0;color:#aaaacc;font-size:16px;">{asset}</p>
            </td>
          </tr>
          <!-- Data Table -->
          <tr>
            <td colspan="2" style="padding:0;">
              <table width="100%" cellpadding="0" cellspacing="0">
                {"".join(rows_html)}
              </table>
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td colspan="2"
                style="background:#f0f0f0;padding:14px 20px;text-align:center;
                       color:#888;font-size:12px;border-top:1px solid #ddd;">
              This is an automated signal alert from Bot Trader.
              {f"Expires in {tenor_days} days." if tenor_days is not None else ""}
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

        # ── Plain text ─────────────────────────────────────────────────────────
        text_lines: list[str] = [
            subject,
            "=" * 40,
            f"Asset: {asset}",
            f"Signal: {label}",
        ]

        if strategy_name is not None:
            text_lines.append(f"Strategy: {strategy_name}")
        if direction is not None:
            text_lines.append(f"Direction: {direction}")
        if tenor_days is not None:
            text_lines.append(f"Tenor: {tenor_days} days")
        if entry_price is not None:
            text_lines.append(f"Entry Price: ${entry_price:,.2f}")
        if confidence is not None:
            text_lines.append(f"Confidence: {confidence * 100:.1f}%")
        if regime is not None:
            text_lines.append(f"Regime: {_format_regime(regime)}")
        if rule_triggered is not None:
            text_lines.append(f"Trigger: {rule_triggered}")
        if indicator_snapshot:
            text_lines.append(f"Indicators: {_format_indicators(indicator_snapshot)}")

        text_lines.append("-" * 40)
        if tenor_days is not None:
            text_lines.append(f"Expires in {tenor_days} days.")
        text_lines.append("This is an automated signal alert from Bot Trader.")

        return {
            "subject": subject,
            "html": html,
            "text": "\n".join(text_lines),
        }
