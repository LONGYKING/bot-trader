import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import NotFoundError
from app.models.backtest import Backtest, BacktestTrade
from app.repositories.backtest import BacktestRepository
from app.repositories.strategy import StrategyRepository


async def submit_backtest(
    session: AsyncSession,
    arq_pool: object,
    data: dict[str, Any],
) -> Backtest:
    """Create a Backtest record and enqueue the run_backtest arq job.

    The ``data`` dict should include at minimum:
        strategy_id, date_from, date_to, initial_capital (optional, defaults to 10000)

    Returns the created Backtest with status='pending'.
    """
    strategy_repo = StrategyRepository(session)
    strategy_id = data.get("strategy_id")
    strategy = await strategy_repo.get_by_id(strategy_id)
    if strategy is None:
        raise NotFoundError("Strategy", str(strategy_id))

    now = datetime.now(UTC)
    backtest_data = {
        "strategy_id": strategy_id,
        "status": "pending",
        "date_from": data["date_from"],
        "date_to": data["date_to"],
        "initial_capital": data.get("initial_capital", 10000),
        "created_at": now,
    }

    repo = BacktestRepository(session)
    backtest = await repo.create(backtest_data)

    # Enqueue the arq job
    job = await arq_pool.enqueue_job("run_backtest", backtest_id=str(backtest.id))

    # Store the arq job id for tracking / cancellation
    job_id = job.job_id if hasattr(job, "job_id") else str(job)
    await repo.update(backtest.id, {"arq_job_id": job_id})
    await session.refresh(backtest)

    return backtest


async def get_backtest(session: AsyncSession, id: uuid.UUID) -> Backtest:
    """Return a backtest by id. Raises NotFoundError if not found."""
    repo = BacktestRepository(session)
    backtest = await repo.get_by_id(id)
    if backtest is None:
        raise NotFoundError("Backtest", str(id))
    return backtest


async def list_backtests(
    session: AsyncSession,
    strategy_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Backtest], int]:
    """Return (items, total_count) with optional strategy_id filter."""
    repo = BacktestRepository(session)

    filters: dict[str, Any] = {}
    if strategy_id is not None:
        filters["strategy_id"] = strategy_id

    items = await repo.list(skip=offset, limit=limit, **filters)
    total = await repo.count(**filters)
    return items, total


async def cancel_backtest(
    session: AsyncSession,
    arq_pool: object,
    id: uuid.UUID,
) -> None:
    """Mark a pending backtest as failed and attempt to abort the arq job.

    Only backtests with status 'pending' or 'running' can be cancelled.
    """
    repo = BacktestRepository(session)
    backtest = await repo.get_by_id(id)
    if backtest is None:
        raise NotFoundError("Backtest", str(id))

    if backtest.status in ("pending", "running"):
        await repo.set_failed(id, "Cancelled by user")

        # Attempt to abort the arq job if we have a job id
        if backtest.arq_job_id:
            try:
                job = arq_pool.job(backtest.arq_job_id)
                await job.abort()
            except Exception:  # noqa: BLE001
                # Best-effort — job may have already completed
                pass


async def get_trades(
    session: AsyncSession,
    backtest_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[BacktestTrade], int]:
    """Return paginated trades for a backtest along with total count."""
    # Ensure backtest exists
    await get_backtest(session, backtest_id)

    repo = BacktestRepository(session)
    items = await repo.get_trades(backtest_id, limit=limit, offset=offset)
    total = await repo.count_trades(backtest_id)
    return items, total


async def get_equity_curve(
    session: AsyncSession,
    backtest_id: uuid.UUID,
) -> list[dict]:
    """Return ordered list of {entry_time, exit_time, pnl_pct} dicts."""
    # Ensure backtest exists
    await get_backtest(session, backtest_id)

    repo = BacktestRepository(session)
    return await repo.get_equity_curve(backtest_id)
