from abc import ABC, abstractmethod
from typing import Any


class AbstractFormatter(ABC):
    @abstractmethod
    def format_signal(self, signal_data: dict) -> Any:
        """Format signal data dict into channel-native message format."""
        ...

    def format_neutral(self, data: dict) -> Any:
        """Format a neutral market-scan update. Override for richer channel output.

        data keys: asset, timeframe, current_price, regime, indicator_snapshot, strategy_name
        """
        asset = data.get("asset", "")
        price = data.get("current_price")
        regime = data.get("regime", "")
        indicators = data.get("indicator_snapshot", {})
        ind_str = " | ".join(f"{k.upper()}: {v:g}" if isinstance(v, float) else f"{k.upper()}: {v}" for k, v in indicators.items())
        lines = [
            f"[SCAN] {asset} — No signal",
            f"Price: {f'${price:,.2f}' if price else 'N/A'} | Regime: {regime.replace('_', ' ').title()}",
        ]
        if ind_str:
            lines.append(f"Indicators: {ind_str}")
        return "\n".join(lines)

    def format_outcome(self, data: dict) -> Any:
        """Format a trade outcome notification. Override for richer channel output.

        data keys: asset, direction, tenor_days, entry_price, exit_price,
                   pnl_pct, is_profitable, entry_time, exit_time
        """
        asset = data.get("asset", "")
        pnl = float(data.get("pnl_pct", 0))
        is_win = pnl > 0
        status = "WIN" if is_win else "LOSS"
        direction = (data.get("direction") or "").upper()
        tenor = data.get("tenor_days")
        entry = data.get("entry_price")
        exit_p = data.get("exit_price")
        lines = [
            f"[{status}] Trade Closed — {asset}",
            f"{direction} {tenor}d | Entry: {'${:,.2f}'.format(entry) if entry else 'N/A'} → Exit: {'${:,.2f}'.format(exit_p) if exit_p else 'N/A'}",
            f"PnL: {pnl:+.2f}%",
        ]
        return "\n".join(lines)

    def format_test(self) -> Any:
        return self.format_signal(
            {
                "asset": "BTC/USDT",
                "signal_value": 7,
                "direction": "CALL",
                "tenor_days": 7,
                "confidence": 0.85,
                "regime": "strong_trend_up",
                "entry_price": 65000.0,
                "rule_triggered": "Test signal — RSI oversold + MACD bullish crossover",
                "indicator_snapshot": {"rsi": 28.5, "macd_hist": 0.0023},
            }
        )
