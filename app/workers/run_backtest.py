"""
run_backtest arq job — full backtest pipeline.

Loads a Backtest record, fetches OHLCV data, runs the backtest engine,
persists trade records, and optionally exports results to Google Sheets.
"""
import uuid
from datetime import UTC, datetime

import structlog

# Import strategies package to trigger class registration
import app.strategies  # noqa: F401
from app.config import get_settings
from app.core.backtest_engine import run_backtest as run_backtest_engine
from app.core.market_data import fetch_ohlcv_range
from app.integrations.cloudinary_upload import upload_to_cloudinary
from app.integrations.google_sheets import export_backtest_to_sheets
from app.integrations.local_export import export_backtest_to_local
from app.repositories.backtest import BacktestRepository
from app.repositories.strategy import StrategyRepository
from app.strategies.registry import StrategyRegistry

logger = structlog.get_logger(__name__)


async def run_backtest(ctx: dict, backtest_id: str) -> dict:
    """Execute the full backtest pipeline for a given backtest record.

    ctx["session_factory"] is an async_sessionmaker set in on_startup.
    ctx["job_id"] is the arq job id.

    Steps:
        1. Load Backtest from DB; if not found or not pending, return early
        2. Set status='running' via repo.set_running(id, arq_job_id=ctx["job_id"])
        3. Load Strategy config
        4. Fetch OHLCV via market_data.fetch_ohlcv_range(...)
        5. Validate >= 200 bars (raised by fetch_ohlcv_range itself)
        6. Instantiate strategy: StrategyRegistry.instantiate(strategy_class, params)
        7. Run: result = run_backtest_engine(strategy, df, initial_capital=...)
        8. Bulk insert BacktestTrade records from result.trades
        9. Export to Google Sheets if google_service_account_json is configured
        10. Call repo.set_completed(id, {all metrics + sheets_url})
        11. Return {"backtest_id": ..., "total_trades": ..., "win_rate": ...}

        On any exception: repo.set_failed(id, str(e)); re-raise
    """
    log = logger.bind(backtest_id=backtest_id)
    log.info("run_backtest.start")

    settings = get_settings()
    backtest_uuid = uuid.UUID(backtest_id)
    job_id = ctx.get("job_id", "")

    async with ctx["session_factory"]() as session:
        async with session.begin():
            repo = BacktestRepository(session)
            backtest = await repo.get_by_id(backtest_uuid)

            if backtest is None:
                log.warning("run_backtest.not_found")
                return {"backtest_id": backtest_id, "status": "not_found"}

            if backtest.status != "pending":
                log.warning("run_backtest.not_pending", status=backtest.status)
                return {"backtest_id": backtest_id, "status": backtest.status}

            # Transition to running
            await repo.set_running(backtest_uuid, arq_job_id=job_id)

    try:
        async with ctx["session_factory"]() as session:
            async with session.begin():
                repo = BacktestRepository(session)
                strategy_repo = StrategyRepository(session)

                # Reload backtest after status update
                backtest = await repo.get_by_id(backtest_uuid)
                if backtest is None:
                    raise ValueError(f"Backtest {backtest_uuid} not found after status update")
                strategy = await strategy_repo.get_by_id(backtest.strategy_id)

                if strategy is None:
                    raise ValueError(f"Strategy {backtest.strategy_id} not found")

                log.info(
                    "run_backtest.fetching_ohlcv",
                    exchange=strategy.exchange,
                    asset=strategy.asset,
                    timeframe=strategy.timeframe,
                    date_from=str(backtest.date_from),
                    date_to=str(backtest.date_to),
                )

                # Convert date objects to datetime (midnight UTC)
                date_from_dt = datetime.combine(backtest.date_from, datetime.min.time()).replace(
                    tzinfo=UTC
                )
                date_to_dt = datetime.combine(backtest.date_to, datetime.min.time()).replace(
                    tzinfo=UTC
                )

                df = await fetch_ohlcv_range(
                    exchange_id=strategy.exchange,
                    symbol=strategy.asset,
                    timeframe=strategy.timeframe,
                    date_from=date_from_dt,
                    date_to=date_to_dt,
                )

                log.info("run_backtest.ohlcv_fetched", bars=len(df))

                # Instantiate strategy and run backtest engine
                strategy_instance = StrategyRegistry.instantiate(strategy.strategy_class, strategy.params)
                trade_type = getattr(strategy, "trade_type", "options") or "options"
                execution_params = dict(getattr(strategy, "execution_params", None) or {})
                result = run_backtest_engine(
                    strategy_instance,
                    df,
                    initial_capital=float(backtest.initial_capital),
                    trade_type=trade_type,
                    execution_params=execution_params,
                )

                log.info(
                    "run_backtest.engine_complete",
                    total_trades=result.total_trades,
                    win_rate=result.win_rate,
                )

                # Bulk insert BacktestTrade records
                if result.trades:
                    trade_dicts = [
                        {
                            "backtest_id": backtest_uuid,
                            "entry_time": t.entry_time.to_pydatetime() if hasattr(t.entry_time, "to_pydatetime") else t.entry_time,
                            "exit_time": t.exit_time.to_pydatetime() if hasattr(t.exit_time, "to_pydatetime") else t.exit_time,
                            "direction": t.direction,
                            "tenor_days": t.tenor_days,
                            "entry_price": t.entry_price,
                            "exit_price": t.exit_price,
                            "pnl_pct": t.pnl_pct,
                            "capital_before": t.capital_before,
                            "capital_after": t.capital_after,
                            "premium_paid": t.premium_paid,
                            "trade_size": t.trade_size,
                            "max_exposure": t.max_exposure,
                            "regime_at_entry": t.regime_at_entry,
                            "rule_trace": t.rule_trace if t.rule_trace else None,
                        }
                        for t in result.trades
                    ]
                    await repo.bulk_insert_trades(trade_dicts)
                    log.info("run_backtest.trades_inserted", count=len(trade_dicts))

                # Always save a local copy first
                local_path = None
                try:
                    local_path = await export_backtest_to_local(
                        result=result,
                        strategy_name=strategy.name,
                        asset=strategy.asset,
                        timeframe=strategy.timeframe,
                        backtest_id=backtest_id,
                        export_dir=settings.backtest_export_dir,
                    )
                except Exception as local_err:
                    log.warning("run_backtest.local_export_failed", error=str(local_err))

                # Try Google Sheets → fall back to Cloudinary if Sheets fails
                sheets_url = None
                if settings.google_service_account_json:
                    try:
                        sheets_url = await export_backtest_to_sheets(
                            result=result,
                            strategy_name=strategy.name,
                            asset=strategy.asset,
                            timeframe=strategy.timeframe,
                            service_account_json=settings.google_service_account_json,
                        )
                    except Exception as sheets_err:
                        log.warning("run_backtest.sheets_export_failed", error=str(sheets_err))
                        # Fall back to Cloudinary if configured
                        if local_path and (settings.cloudinary_url or settings.cloudinary_cloud_name):
                            try:
                                sheets_url = await upload_to_cloudinary(
                                    file_path=local_path,
                                    public_id=f"backtests/{backtest_id}",
                                    cloudinary_url=settings.cloudinary_url,
                                    cloud_name=settings.cloudinary_cloud_name,
                                    api_key=settings.cloudinary_api_key,
                                    api_secret=settings.cloudinary_api_secret,
                                )
                                log.info("run_backtest.cloudinary_fallback_ok", url=sheets_url)
                            except Exception as cld_err:
                                log.warning("run_backtest.cloudinary_export_failed", error=str(cld_err))

                # Persist final metrics
                metrics = {
                    "total_trades": result.total_trades,
                    "winning_trades": result.winning_trades,
                    "win_rate": result.win_rate,
                    "total_pnl_pct": result.total_pnl_pct,
                    "sharpe_ratio": result.sharpe_ratio,
                    "max_drawdown_pct": result.max_drawdown_pct,
                    "annual_return_pct": result.annual_return_pct,
                    "sheets_url": sheets_url,
                }
                await repo.set_completed(backtest_uuid, metrics)

        log.info(
            "run_backtest.complete",
            total_trades=result.total_trades,
            win_rate=result.win_rate,
        )
        return {
            "backtest_id": backtest_id,
            "total_trades": result.total_trades,
            "win_rate": result.win_rate,
        }

    except Exception as exc:
        log.exception("run_backtest.failed", error=str(exc))
        # Persist failure status
        try:
            async with ctx["session_factory"]() as session:
                async with session.begin():
                    repo = BacktestRepository(session)
                    await repo.set_failed(backtest_uuid, str(exc))
        except Exception as inner_exc:  # noqa: BLE001
            log.exception("run_backtest.set_failed_error", error=str(inner_exc))
        raise
