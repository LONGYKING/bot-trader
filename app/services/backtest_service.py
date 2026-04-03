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
    tenant_id: uuid.UUID | None = None,
) -> Backtest:
    strategy_repo = StrategyRepository(session, tenant_id)
    strategy_id = data.get("strategy_id")
    if strategy_id is None:
        raise NotFoundError("Strategy", "None")
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
    if tenant_id is not None:
        backtest_data["tenant_id"] = tenant_id

    repo = BacktestRepository(session, tenant_id)
    backtest = await repo.create(backtest_data)

    job = await arq_pool.enqueue_job("run_backtest", backtest_id=str(backtest.id))  # type: ignore[attr-defined]
    job_id = job.job_id if hasattr(job, "job_id") else str(job)
    await repo.update(backtest.id, {"arq_job_id": job_id})
    await session.refresh(backtest)

    return backtest


async def get_backtest(
    session: AsyncSession,
    id: uuid.UUID,
    tenant_id: uuid.UUID | None = None,
) -> Backtest:
    repo = BacktestRepository(session, tenant_id)
    backtest = await repo.get_by_id(id)
    if backtest is None:
        raise NotFoundError("Backtest", str(id))
    return backtest


async def list_backtests(
    session: AsyncSession,
    tenant_id: uuid.UUID | None = None,
    strategy_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Backtest], int]:
    repo = BacktestRepository(session, tenant_id)
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
    tenant_id: uuid.UUID | None = None,
) -> None:
    repo = BacktestRepository(session, tenant_id)
    backtest = await repo.get_by_id(id)
    if backtest is None:
        raise NotFoundError("Backtest", str(id))

    if backtest.status in ("pending", "running"):
        await repo.set_failed(id, "Cancelled by user")
        if backtest.arq_job_id:
            try:
                job = arq_pool.job(backtest.arq_job_id)  # type: ignore[attr-defined]
                await job.abort()
            except Exception:  # noqa: BLE001
                pass


async def get_trades(
    session: AsyncSession,
    backtest_id: uuid.UUID,
    tenant_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[BacktestTrade], int]:
    await get_backtest(session, backtest_id, tenant_id=tenant_id)
    repo = BacktestRepository(session, tenant_id)
    items = await repo.get_trades(backtest_id, limit=limit, offset=offset)
    total = await repo.count_trades(backtest_id)
    return items, total


async def get_equity_curve(
    session: AsyncSession,
    backtest_id: uuid.UUID,
    tenant_id: uuid.UUID | None = None,
) -> list[dict]:
    await get_backtest(session, backtest_id, tenant_id=tenant_id)
    repo = BacktestRepository(session, tenant_id)
    return await repo.get_equity_curve(backtest_id)
