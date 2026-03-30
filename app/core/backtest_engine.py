"""
Backtest engine with pluggable execution models.

Signal convention
-----------------
  +7  → strong bullish (strong CALL / strong LONG)
  +3  → weak   bullish (weak CALL   / weak LONG)
  -3  → weak   bearish (weak PUT    / weak SHORT)
  -7  → strong bearish (strong PUT  / strong SHORT)
   0  → no trade

Execution models
----------------
  options  — premium risk, tenor-based exits, profit cap (existing behaviour)
  spot     — position-size % of capital, stop-loss / take-profit / hold_bars exit
  futures  — stub (raises NotImplementedError)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from app.strategies.base import BaseStrategy


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class TradeRecord:
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    direction: str          # "CALL"/"PUT" (options) or "LONG"/"SHORT" (spot/futures)
    tenor_days: int | None  # options only; None for spot/futures
    entry_price: float
    exit_price: float
    pnl_pct: float          # percentage (e.g. 5.2 means +5.2 %)
    capital_before: float = 0.0
    capital_after: float = 0.0
    premium_paid: float = 0.0
    trade_size: float = 0.0
    max_exposure: float = 0.0
    regime_at_entry: str | None = None
    rule_trace: dict = field(default_factory=dict)


@dataclass
class BacktestResult:
    strategy_name: str
    asset: str
    timeframe: str
    date_from: str
    date_to: str
    initial_capital: float
    total_trades: int
    winning_trades: int
    win_rate: float
    total_pnl_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    annual_return_pct: float
    trades: list[TradeRecord] = field(default_factory=list)
    equity_curve: list[dict] = field(default_factory=list)
    error: str | None = None


# ---------------------------------------------------------------------------
# Execution models
# ---------------------------------------------------------------------------

class OptionsExecutionModel:
    """
    Options-style simulation.

    Capital model per trade:
        risk  = capital * premium_pct
        win   → capital *= (1 + min(pnl_frac, profit_cap_pct))
        loss  → capital *= (1 - premium_pct)   # lose only the premium

    Default execution_params:
        premium_pct       = 0.025   (2.5 % cost to enter)
        profit_cap_pct    = 0.10    (10 % max profit per trade)
        tenor_days_weak   = 3
        tenor_days_strong = 7
    """

    _DEFAULTS = {
        "premium_pct": 0.025,
        "profit_cap_pct": 0.10,
        "tenor_days_weak": 3,
        "tenor_days_strong": 7,
    }

    def __init__(self, execution_params: dict) -> None:
        p = {**self._DEFAULTS, **execution_params}
        self.premium_pct = float(p["premium_pct"])
        self.profit_cap_pct = float(p["profit_cap_pct"])
        self.tenor_days_weak = int(p["tenor_days_weak"])
        self.tenor_days_strong = int(p["tenor_days_strong"])

    def simulate(
        self,
        signal_series: pd.Series,
        df: pd.DataFrame,
        initial_capital: float,
    ) -> tuple[list[TradeRecord], list[dict]]:
        close = df["close"]
        n = len(df)
        cap = initial_capital
        trades: list[TradeRecord] = []
        equity_curve: list[dict] = [
            {"time": df.index[0].isoformat(), "value": round(cap, 2)}
        ]

        i = 0
        while i < n:
            sig = int(signal_series.iloc[i])
            if sig == 0:
                i += 1
                continue

            direction = "CALL" if sig > 0 else "PUT"
            tenor_days = self.tenor_days_strong if abs(sig) == 7 else self.tenor_days_weak
            tenor_bars = tenor_days  # 1 bar ≈ 1 day for daily; caller adjusts via subclass

            entry_price = float(close.iloc[i])
            entry_time = df.index[i]

            exit_idx = min(i + tenor_bars, n - 1)
            exit_price = float(close.iloc[exit_idx])
            exit_time = df.index[exit_idx]

            # Early exit on profit cap
            for j in range(i + 1, exit_idx + 1):
                p = float(close.iloc[j])
                interim = (
                    (p - entry_price) / entry_price
                    if direction == "CALL"
                    else (entry_price - p) / entry_price
                )
                if interim >= self.profit_cap_pct:
                    exit_price = p
                    exit_time = df.index[j]
                    exit_idx = j
                    break

            pnl_frac = (
                (exit_price - entry_price) / entry_price
                if direction == "CALL"
                else (entry_price - exit_price) / entry_price
            )
            pnl_frac = min(pnl_frac, self.profit_cap_pct)

            capital_before = round(cap, 2)
            premium_paid = round(cap * self.premium_pct, 2)
            trade_size = capital_before
            max_exposure = premium_paid

            cap = cap * (1.0 + pnl_frac) if pnl_frac > 0 else cap * (1.0 - self.premium_pct)
            capital_after = round(cap, 2)

            trades.append(TradeRecord(
                entry_time=entry_time,
                exit_time=exit_time,
                direction=direction,
                tenor_days=tenor_days,
                entry_price=entry_price,
                exit_price=exit_price,
                pnl_pct=round(pnl_frac * 100, 4),
                capital_before=capital_before,
                capital_after=capital_after,
                premium_paid=premium_paid,
                trade_size=trade_size,
                max_exposure=max_exposure,
            ))
            equity_curve.append({"time": exit_time.isoformat(), "value": round(cap, 2)})
            i = exit_idx + 1

        return trades, equity_curve


class SpotExecutionModel:
    """
    Spot trading simulation.

    Enters a position of `position_size_pct` of capital per trade.
    Exits on take-profit, stop-loss, or after hold_bars.

    Default execution_params:
        position_size_pct = 0.10   (10 % of capital per trade)
        stop_loss_pct     = 0.05   (5 % stop loss)
        take_profit_pct   = 0.15   (15 % take profit)
        hold_bars         = 20     (max bars to hold if no TP/SL)
    """

    _DEFAULTS = {
        "position_size_pct": 0.10,
        "stop_loss_pct": 0.05,
        "take_profit_pct": 0.15,
        "hold_bars": 20,
    }

    def __init__(self, execution_params: dict) -> None:
        p = {**self._DEFAULTS, **execution_params}
        self.position_size_pct = float(p["position_size_pct"])
        self.stop_loss_pct = float(p["stop_loss_pct"])
        self.take_profit_pct = float(p["take_profit_pct"])
        self.hold_bars = int(p["hold_bars"])

    def simulate(
        self,
        signal_series: pd.Series,
        df: pd.DataFrame,
        initial_capital: float,
    ) -> tuple[list[TradeRecord], list[dict]]:
        close = df["close"]
        n = len(df)
        cap = initial_capital
        trades: list[TradeRecord] = []
        equity_curve: list[dict] = [
            {"time": df.index[0].isoformat(), "value": round(cap, 2)}
        ]

        i = 0
        while i < n:
            sig = int(signal_series.iloc[i])
            if sig == 0:
                i += 1
                continue

            direction = "LONG" if sig > 0 else "SHORT"
            entry_price = float(close.iloc[i])
            entry_time = df.index[i]
            position_value = cap * self.position_size_pct

            exit_idx = min(i + self.hold_bars, n - 1)
            exit_price = float(close.iloc[exit_idx])
            exit_time = df.index[exit_idx]

            # Scan for TP / SL before hold_bars expiry
            for j in range(i + 1, exit_idx + 1):
                p = float(close.iloc[j])
                move = (
                    (p - entry_price) / entry_price
                    if direction == "LONG"
                    else (entry_price - p) / entry_price
                )
                if move >= self.take_profit_pct:
                    exit_price = p
                    exit_time = df.index[j]
                    exit_idx = j
                    break
                if move <= -self.stop_loss_pct:
                    exit_price = p
                    exit_time = df.index[j]
                    exit_idx = j
                    break

            pnl_frac = (
                (exit_price - entry_price) / entry_price
                if direction == "LONG"
                else (entry_price - exit_price) / entry_price
            )

            capital_before = round(cap, 2)
            trade_size = round(position_value, 2)
            max_exposure = round(position_value * self.stop_loss_pct, 2)
            # premium_paid reused as amount at risk (position_value)
            premium_paid = trade_size

            cap = cap + position_value * pnl_frac
            capital_after = round(cap, 2)

            trades.append(TradeRecord(
                entry_time=entry_time,
                exit_time=exit_time,
                direction=direction,
                tenor_days=None,
                entry_price=entry_price,
                exit_price=exit_price,
                pnl_pct=round(pnl_frac * 100, 4),
                capital_before=capital_before,
                capital_after=capital_after,
                premium_paid=premium_paid,
                trade_size=trade_size,
                max_exposure=max_exposure,
            ))
            equity_curve.append({"time": exit_time.isoformat(), "value": round(cap, 2)})
            i = exit_idx + 1

        return trades, equity_curve


class FuturesExecutionModel:
    """Futures execution — planned, not yet implemented."""

    def __init__(self, execution_params: dict) -> None:
        self.execution_params = execution_params

    def simulate(self, *_args, **_kwargs):  # noqa: ANN002
        raise NotImplementedError(
            "Futures backtesting is not yet supported. "
            "Use trade_type='options' or trade_type='spot'."
        )


_EXECUTION_MODELS: dict[str, type] = {
    "options": OptionsExecutionModel,
    "spot": SpotExecutionModel,
    "futures": FuturesExecutionModel,
}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_backtest(
    strategy: "BaseStrategy",
    df: pd.DataFrame,
    initial_capital: float = 10_000.0,
    trade_type: str = "options",
    execution_params: dict | None = None,
) -> BacktestResult:
    """
    Run a bar-by-bar backtest using the execution model for *trade_type*.

    Parameters
    ----------
    strategy:
        Instantiated BaseStrategy.
    df:
        OHLCV DataFrame with at least a ``close`` column.
    initial_capital:
        Starting portfolio value in USD.
    trade_type:
        ``"options"``, ``"spot"``, or ``"futures"``.
    execution_params:
        Overrides for the execution model defaults.  See each model's
        ``_DEFAULTS`` dict for available keys.
    """
    if trade_type not in _EXECUTION_MODELS:
        raise ValueError(
            f"Unknown trade_type '{trade_type}'. "
            f"Supported: {list(_EXECUTION_MODELS)}"
        )

    signal_series = strategy.generate_signal_series(df)
    model_cls = _EXECUTION_MODELS[trade_type]
    model = model_cls(execution_params or {})
    trades, equity_curve = model.simulate(signal_series, df, initial_capital)

    return _build_result(strategy, df, initial_capital, trades, equity_curve)


# ---------------------------------------------------------------------------
# Result builder (shared across models)
# ---------------------------------------------------------------------------

def _build_result(
    strategy: "BaseStrategy",
    df: pd.DataFrame,
    initial_capital: float,
    trades: list[TradeRecord],
    equity_curve: list[dict],
) -> BacktestResult:
    total_trades = len(trades)

    if total_trades == 0:
        return BacktestResult(
            strategy_name=strategy.name,
            asset="",
            timeframe="",
            date_from=df.index[0].isoformat(),
            date_to=df.index[-1].isoformat(),
            initial_capital=initial_capital,
            total_trades=0,
            winning_trades=0,
            win_rate=0.0,
            total_pnl_pct=0.0,
            sharpe_ratio=0.0,
            max_drawdown_pct=0.0,
            annual_return_pct=0.0,
            trades=[],
            equity_curve=equity_curve,
        )

    winning_trades = sum(1 for t in trades if t.pnl_pct > 0)
    win_rate = winning_trades / total_trades

    final_capital = equity_curve[-1]["value"]
    total_pnl_pct = ((final_capital - initial_capital) / initial_capital) * 100.0

    pnl_series = pd.Series([t.pnl_pct / 100.0 for t in trades])
    sharpe = (
        float((pnl_series.mean() / pnl_series.std()) * np.sqrt(total_trades))
        if pnl_series.std() > 0
        else 0.0
    )

    equity_arr = np.array([e["value"] for e in equity_curve], dtype=float)
    peak = np.maximum.accumulate(equity_arr)
    drawdown = (equity_arr - peak) / np.where(peak == 0, 1.0, peak)
    max_drawdown_pct = float(abs(drawdown.min()) * 100)

    total_days = max((df.index[-1] - df.index[0]).days, 1)
    years = total_days / 365.0
    annual_return_pct = (
        float(((final_capital / initial_capital) ** (1.0 / years) - 1.0) * 100)
        if years > 0 and initial_capital > 0
        else 0.0
    )

    return BacktestResult(
        strategy_name=strategy.name,
        asset="",
        timeframe="",
        date_from=df.index[0].isoformat(),
        date_to=df.index[-1].isoformat(),
        initial_capital=initial_capital,
        total_trades=total_trades,
        winning_trades=winning_trades,
        win_rate=round(win_rate, 4),
        total_pnl_pct=round(total_pnl_pct, 4),
        sharpe_ratio=round(sharpe, 4),
        max_drawdown_pct=round(max_drawdown_pct, 4),
        annual_return_pct=round(annual_return_pct, 4),
        trades=trades,
        equity_curve=equity_curve,
    )
