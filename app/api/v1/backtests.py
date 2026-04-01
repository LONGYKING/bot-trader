import uuid
from typing import Annotated

from arq import ArqRedis
from fastapi import APIRouter, Depends, status

from app.db.redis import get_arq_pool
from app.dependencies import DBSession, PaginationParams, require_scope
from app.models.api_key import ApiKey
from app.schemas.backtest import BacktestCreate, BacktestResponse, BacktestTradeResponse
from app.schemas.common import PaginatedResponse
from app.services import backtest_service

router = APIRouter(prefix="/backtests")


@router.post("", response_model=BacktestResponse, status_code=status.HTTP_202_ACCEPTED)
async def submit_backtest(
    body: BacktestCreate,
    session: DBSession,
    redis: Annotated[ArqRedis, Depends(get_arq_pool)],
    _: ApiKey = Depends(require_scope("write:strategies")),
):
    """Submit a backtest job. Returns 202 Accepted."""
    return await backtest_service.submit_backtest(session, redis, body.model_dump())


@router.get("", response_model=PaginatedResponse[BacktestResponse])
async def list_backtests(
    session: DBSession,
    _: ApiKey = Depends(require_scope("read:strategies")),
    strategy_id: uuid.UUID | None = None,
    pagination: PaginationParams = Depends(),
):
    """List backtests with optional strategy_id filter. Paginated."""
    items, total = await backtest_service.list_backtests(
        session,
        strategy_id=strategy_id,
        limit=pagination.limit,
        offset=pagination.skip,
    )
    pages = max(1, (total + pagination.page_size - 1) // pagination.page_size)
    return PaginatedResponse(
        items=items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        pages=pages,
    )


@router.get("/{id}", response_model=BacktestResponse)
async def get_backtest(
    id: uuid.UUID,
    session: DBSession,
    _: ApiKey = Depends(require_scope("read:strategies")),
):
    """Get backtest status and results by id."""
    return await backtest_service.get_backtest(session, id)


@router.get("/{id}/trades", response_model=PaginatedResponse[BacktestTradeResponse])
async def get_backtest_trades(
    id: uuid.UUID,
    session: DBSession,
    _: ApiKey = Depends(require_scope("read:strategies")),
    pagination: PaginationParams = Depends(),
):
    """Return paginated trade log for a backtest."""
    items, total = await backtest_service.get_trades(
        session,
        backtest_id=id,
        limit=pagination.limit,
        offset=pagination.skip,
    )
    pages = max(1, (total + pagination.page_size - 1) // pagination.page_size)
    return PaginatedResponse(
        items=items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        pages=pages,
    )


@router.get("/{id}/equity-curve")
async def get_equity_curve(
    id: uuid.UUID,
    session: DBSession,
    _: ApiKey = Depends(require_scope("read:strategies")),
):
    """Return equity curve data for a backtest as a list of trade snapshots."""
    return await backtest_service.get_equity_curve(session, id)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_backtest(
    id: uuid.UUID,
    session: DBSession,
    redis: Annotated[ArqRedis, Depends(get_arq_pool)],
    _: ApiKey = Depends(require_scope("write:strategies")),
):
    """Cancel a pending or running backtest."""
    await backtest_service.cancel_backtest(session, redis, id)
