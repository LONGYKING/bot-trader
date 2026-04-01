"""
Google Sheets integration for backtest export.
Authenticated via service account JSON stored in GOOGLE_SERVICE_ACCOUNT_JSON env var.
Creates three tabs: Summary, Trades, Equity Curve.
Shares with "anyone with link → viewer".
Returns the spreadsheet URL.
"""
import asyncio
import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import gspread_asyncio
from google.oauth2.service_account import Credentials

if TYPE_CHECKING:
    from app.core.backtest_engine import BacktestResult

SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

def _get_credentials_factory(service_account_json: str):
    """Returns a credentials factory function for gspread_asyncio."""
    def make_credentials():
        info = json.loads(service_account_json)
        creds = Credentials.from_service_account_info(info, scopes=SCOPES)
        return creds
    return make_credentials


async def export_backtest_to_sheets(
    result: "BacktestResult",
    strategy_name: str,
    asset: str,
    timeframe: str,
    service_account_json: str,
) -> str:
    """
    Export a BacktestResult to a new Google Spreadsheet.
    Returns the shareable URL.

    Creates:
    - Tab 1: "Summary" — key/value pairs of all metrics
    - Tab 2: "Trades" — one row per BacktestTrade
    - Tab 3: "Equity Curve" — time + portfolio value

    Shares with anyone (viewer) so the URL is directly usable.
    """
    agc_manager = gspread_asyncio.AsyncioGspreadClientManager(_get_credentials_factory(service_account_json))
    agc = await agc_manager.authorize()

    title = f"{strategy_name} — {asset} {timeframe} Backtest ({result.date_from[:10]} to {result.date_to[:10]})"
    spreadsheet = await agc.create(title)

    # Share with anyone as viewer
    # gspread uses synchronous drive API for sharing — run in thread
    await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: spreadsheet.spreadsheet.share(None, perm_type="anyone", role="reader")
    )

    # --- Tab 1: Summary ---
    summary_sheet = await spreadsheet.get_sheet1()
    await summary_sheet.update_title("Summary")

    summary_rows = [
        ["Metric", "Value"],
        ["Strategy", strategy_name],
        ["Asset", asset],
        ["Timeframe", timeframe],
        ["Period", f"{result.date_from[:10]} to {result.date_to[:10]}"],
        ["Initial Capital", f"${result.initial_capital:,.2f}"],
        ["Total Trades", result.total_trades],
        ["Winning Trades", result.winning_trades],
        ["Win Rate", f"{result.win_rate * 100:.1f}%"],
        ["Total PnL %", f"{result.total_pnl_pct:.2f}%"],
        ["Sharpe Ratio", f"{result.sharpe_ratio:.2f}"],
        ["Max Drawdown %", f"{result.max_drawdown_pct:.2f}%"],
        ["Annual Return %", f"{result.annual_return_pct:.2f}%"],
        ["Generated At", datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")],
    ]
    await summary_sheet.update("A1", summary_rows)

    # --- Tab 2: Trades ---
    trades_sheet = await spreadsheet.add_worksheet(title="Trades", rows=max(len(result.trades) + 2, 10), cols=13)

    trade_headers = [
        "Entry Time", "Exit Time", "Direction", "Tenor (days)",
        "Entry Price", "Exit Price", "PnL %",
        "Capital Before ($)", "Capital After ($)", "Premium Paid ($)",
        "Trade Size ($)", "Max Exposure ($)", "Regime",
    ]
    trade_rows: list[list[Any]] = [trade_headers]
    for t in result.trades:
        trade_rows.append([
            str(t.entry_time)[:19] if hasattr(t.entry_time, '__str__') else t.entry_time,
            str(t.exit_time)[:19] if hasattr(t.exit_time, '__str__') else t.exit_time,
            t.direction,
            t.tenor_days,
            float(t.entry_price),
            float(t.exit_price),
            float(t.pnl_pct),
            float(t.capital_before),
            float(t.capital_after),
            float(t.premium_paid),
            float(t.trade_size),
            float(t.max_exposure),
            t.regime_at_entry or "",
        ])
    if len(trade_rows) > 1:
        await trades_sheet.update("A1", trade_rows)

    # --- Tab 3: Equity Curve ---
    equity_sheet = await spreadsheet.add_worksheet(title="Equity Curve", rows=max(len(result.equity_curve) + 2, 10), cols=3)

    equity_headers = ["Time", "Portfolio Value"]
    equity_rows: list[list[Any]] = [equity_headers]
    for point in result.equity_curve:
        equity_rows.append([
            str(point["time"])[:19],
            float(point["value"]),
        ])
    if len(equity_rows) > 1:
        await equity_sheet.update("A1", equity_rows)

    spreadsheet_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet.id}"
    return spreadsheet_url
