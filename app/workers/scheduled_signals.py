"""
scheduled_signals arq job — runs every 5 minutes.

Each strategy has its own configurable interval (strategy.interval_minutes,
default 15). A Redis key tracks the last run time per strategy so strategies
with longer intervals are skipped on cycles that fall within their cooldown.
"""
import time

import structlog

from app.repositories.strategy import StrategyRepository
from app.services import signal_service

logger = structlog.get_logger(__name__)


async def scheduled_signals(ctx: dict) -> dict:
    """Generate signals for all active strategies.

    ctx["session_factory"] is an async_sessionmaker set in on_startup.
    ctx["redis"] is the arq Redis pool (passed to signal_service for enqueueing).

    Steps:
        1. Query all active strategies from DB
        2. For each strategy, call signal_service.generate_signal(session, arq_pool, strategy.id)
           — skip if exception (log error, continue)
        3. Return {"strategies_processed": n, "signals_generated": m}
    """
    log = logger.bind(job="scheduled_signals")
    log.info("scheduled_signals.start")

    arq_pool = ctx["redis"]
    strategies_processed = 0
    signals_generated = 0

    try:
        async with ctx["session_factory"]() as session:
            strategy_repo = StrategyRepository(session)
            active_strategies = await strategy_repo.list_active()

        log.info("scheduled_signals.strategies_found", count=len(active_strategies))

        redis = ctx["redis"]

        for strategy in active_strategies:
            strategy_log = log.bind(strategy_id=str(strategy.id), strategy_name=strategy.name)

            # Per-strategy interval check
            last_run_key = f"signal:last_run:{strategy.id}"
            last_run = await redis.get(last_run_key)
            if last_run:
                elapsed = time.time() - float(last_run)
                interval_seconds = strategy.interval_minutes * 60
                if elapsed < interval_seconds:
                    strategy_log.debug(
                        "scheduled_signals.interval_not_reached",
                        elapsed_seconds=round(elapsed),
                        interval_minutes=strategy.interval_minutes,
                    )
                    continue

            strategies_processed += 1
            try:
                async with ctx["session_factory"]() as session:
                    async with session.begin():
                        signal = await signal_service.generate_signal(
                            session=session,
                            arq_pool=arq_pool,
                            strategy_id=strategy.id,
                        )

                if signal is not None:
                    signals_generated += 1
                    strategy_log.info(
                        "scheduled_signals.signal_generated",
                        signal_id=str(signal.id),
                        signal_value=signal.signal_value,
                    )
                else:
                    strategy_log.debug("scheduled_signals.neutral_signal")

            except Exception as exc:  # noqa: BLE001
                strategy_log.exception("scheduled_signals.strategy_error", error=str(exc))
            finally:
                # Record last run time regardless of outcome
                ttl = strategy.interval_minutes * 60 * 2
                await redis.set(last_run_key, str(time.time()), ex=ttl)

    except Exception as exc:  # noqa: BLE001
        log.exception("scheduled_signals.failed", error=str(exc))

    log.info(
        "scheduled_signals.complete",
        strategies_processed=strategies_processed,
        signals_generated=signals_generated,
    )
    return {
        "strategies_processed": strategies_processed,
        "signals_generated": signals_generated,
    }
