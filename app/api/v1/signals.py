import uuid
from datetime import datetime
from typing import Annotated

from arq import ArqRedis
from fastapi import APIRouter, Depends, HTTPException, status

from app.db.redis import get_arq_pool
from app.dependencies import CurrentTenant, DBSession, PaginationParams
from app.schemas.common import PaginatedResponse
from app.schemas.delivery import DeliveryResponse
from app.schemas.outcome import OutcomeResponse
from app.schemas.signal import (
    SignalForceRequest,
    SignalGenerateRequest,
    SignalResponse,
)
from app.core.plan_limits import get_effective_limits
from app.models.tenant import Tenant
from app.repositories.signal import SignalRepository
from app.services import delivery_service, outcome_service, signal_service

router = APIRouter(prefix="/signals")


@router.get("", response_model=PaginatedResponse[SignalResponse])
async def list_signals(
    tenant: CurrentTenant,
    session: DBSession,
    strategy_id: uuid.UUID | None = None,
    asset: str | None = None,
    signal_value: int | None = None,
    from_dt: str | None = None,
    to_dt: str | None = None,
    is_profitable: bool | None = None,
    pagination: PaginationParams = Depends(),
):
    filters: dict = {}
    if strategy_id is not None:
        filters["strategy_id"] = strategy_id
    if asset is not None:
        filters["asset"] = asset
    if signal_value is not None:
        filters["signal_value"] = signal_value

    parsed_from = datetime.fromisoformat(from_dt) if from_dt is not None else None
    parsed_to = datetime.fromisoformat(to_dt) if to_dt is not None else None
    if parsed_from is not None and parsed_to is not None and parsed_from > parsed_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="from_dt must be before to_dt",
        )
    if parsed_from is not None:
        filters["from_dt"] = parsed_from
    if parsed_to is not None:
        filters["to_dt"] = parsed_to
    if is_profitable is not None:
        filters["is_profitable"] = is_profitable

    items, total = await signal_service.list_signals(
        session,
        tenant_id=tenant.id,
        filters=filters,
        limit=pagination.limit,
        offset=pagination.skip,
    )
    pages = max(1, (total + pagination.page_size - 1) // pagination.page_size)
    return PaginatedResponse(items=items, total=total, page=pagination.page,
                             page_size=pagination.page_size, pages=pages)


async def _check_signal_limits(session: DBSession, tenant: Tenant) -> None:
    limits = await get_effective_limits(session, tenant)
    sig_repo = SignalRepository(session, tenant.id)
    if limits.max_signals_per_day != -1:
        today_count = await sig_repo.count_today(tenant.id)
        if today_count >= limits.max_signals_per_day:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Daily signal limit reached ({limits.max_signals_per_day}/day). Upgrade your plan for more signals.",
            )
    if limits.max_signals_per_month != -1:
        month_count = await sig_repo.count_this_month(tenant.id)
        if month_count >= limits.max_signals_per_month:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Monthly signal limit reached ({limits.max_signals_per_month}/month). Upgrade your plan for more signals.",
            )


@router.post("/generate")
async def generate_signal(
    body: SignalGenerateRequest,
    tenant: CurrentTenant,
    session: DBSession,
    redis: Annotated[ArqRedis, Depends(get_arq_pool)],
):
    await _check_signal_limits(session, tenant)
    signal = await signal_service.generate_signal(session, redis, body.strategy_id, tenant_id=tenant.id)
    if signal is None:
        return {"message": "No signal generated (neutral)", "signal": None}
    return {"message": "Signal generated", "signal": SignalResponse.model_validate(signal)}


@router.post("/force")
async def force_signal(
    body: SignalForceRequest,
    tenant: CurrentTenant,
    session: DBSession,
    redis: Annotated[ArqRedis, Depends(get_arq_pool)],
):
    await _check_signal_limits(session, tenant)
    signal = await signal_service.force_signal(
        session, redis, body.strategy_id, body.signal_value, body.entry_price, tenant_id=tenant.id
    )
    return {"message": "Signal forced", "signal": SignalResponse.model_validate(signal)}


@router.get("/{id}", response_model=SignalResponse)
async def get_signal(
    id: uuid.UUID,
    tenant: CurrentTenant,
    session: DBSession,
):
    return await signal_service.get_signal(session, id, tenant_id=tenant.id)


@router.get("/{id}/deliveries", response_model=list[DeliveryResponse])
async def get_signal_deliveries(
    id: uuid.UUID,
    tenant: CurrentTenant,
    session: DBSession,
):
    await signal_service.get_signal(session, id, tenant_id=tenant.id)
    return await delivery_service.get_deliveries_for_signal(session, id, tenant_id=tenant.id)


@router.get("/{id}/outcome", response_model=OutcomeResponse)
async def get_signal_outcome(
    id: uuid.UUID,
    tenant: CurrentTenant,
    session: DBSession,
):
    return await outcome_service.get_outcome(session, id, tenant_id=tenant.id)
