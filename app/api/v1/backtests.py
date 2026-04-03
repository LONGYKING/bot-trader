import uuid
from typing import Annotated

from arq import ArqRedis
from fastapi import APIRouter, Depends, status

from app.core.plan_limits import get_effective_limits
from app.db.redis import get_arq_pool
from app.dependencies import CurrentTenant, DBSession, PaginationParams
from app.schemas.backtest import BacktestCreate, BacktestResponse, BacktestTradeResponse
from app.schemas.common import PaginatedResponse
from app.services import backtest_service

router = APIRouter(prefix="/backtests")


@router.post("", response_model=BacktestResponse, status_code=status.HTTP_202_ACCEPTED)
async def submit_backtest(
    body: BacktestCreate,
    tenant: CurrentTenant,
    session: DBSession,
    redis: Annotated[ArqRedis, Depends(get_arq_pool)],
):
    limits = await get_effective_limits(session, tenant)
    limits.check_feature("backtest")
    from app.repositories.backtest import BacktestRepository
    month_count = await BacktestRepository(session, tenant.id).count_this_month(tenant.id)
    limits.check_capacity("backtests_per_month", month_count)
    data = body.model_dump()
    data["tenant_id"] = tenant.id
    return await backtest_service.submit_backtest(session, redis, data, tenant_id=tenant.id)


@router.get("", response_model=PaginatedResponse[BacktestResponse])
async def list_backtests(
    tenant: CurrentTenant,
    session: DBSession,
    strategy_id: uuid.UUID | None = None,
    pagination: PaginationParams = Depends(),
):
    items, total = await backtest_service.list_backtests(
        session,
        tenant_id=tenant.id,
        strategy_id=strategy_id,
        limit=pagination.limit,
        offset=pagination.skip,
    )
    pages = max(1, (total + pagination.page_size - 1) // pagination.page_size)
    return PaginatedResponse(items=items, total=total, page=pagination.page,
                             page_size=pagination.page_size, pages=pages)


@router.get("/{id}", response_model=BacktestResponse)
async def get_backtest(
    id: uuid.UUID,
    tenant: CurrentTenant,
    session: DBSession,
):
    return await backtest_service.get_backtest(session, id, tenant_id=tenant.id)


@router.get("/{id}/trades", response_model=PaginatedResponse[BacktestTradeResponse])
async def get_backtest_trades(
    id: uuid.UUID,
    tenant: CurrentTenant,
    session: DBSession,
    pagination: PaginationParams = Depends(),
):
    items, total = await backtest_service.get_trades(
        session,
        backtest_id=id,
        tenant_id=tenant.id,
        limit=pagination.limit,
        offset=pagination.skip,
    )
    pages = max(1, (total + pagination.page_size - 1) // pagination.page_size)
    return PaginatedResponse(items=items, total=total, page=pagination.page,
                             page_size=pagination.page_size, pages=pages)


@router.get("/{id}/equity-curve")
async def get_equity_curve(
    id: uuid.UUID,
    tenant: CurrentTenant,
    session: DBSession,
):
    return await backtest_service.get_equity_curve(session, id, tenant_id=tenant.id)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_backtest(
    id: uuid.UUID,
    tenant: CurrentTenant,
    session: DBSession,
    redis: Annotated[ArqRedis, Depends(get_arq_pool)],
):
    await backtest_service.cancel_backtest(session, redis, id, tenant_id=tenant.id)
