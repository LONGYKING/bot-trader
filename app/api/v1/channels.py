import uuid

from fastapi import APIRouter, Depends, status

from app.core.plan_limits import get_effective_limits
from app.dependencies import CurrentTenant, DBSession, PaginationParams
from app.schemas.channel import ChannelCreate, ChannelResponse, ChannelTestResponse, ChannelUpdate
from app.schemas.delivery import DeliveryResponse
from app.services import channel_service, delivery_service

router = APIRouter(prefix="/channels")


@router.get("", response_model=list[ChannelResponse])
async def list_channels(
    tenant: CurrentTenant,
    session: DBSession,
    pagination: PaginationParams = Depends(),
):
    items = await channel_service.list_channels(
        session, tenant_id=tenant.id, limit=pagination.limit, offset=pagination.skip
    )
    return [ChannelResponse.from_channel(ch) for ch in items]


@router.post("", response_model=ChannelResponse, status_code=status.HTTP_201_CREATED)
async def create_channel(
    body: ChannelCreate,
    tenant: CurrentTenant,
    session: DBSession,
):
    limits = await get_effective_limits(session, tenant)
    limits.check_channel_type(body.channel_type)
    if body.channel_type == "exchange" and not limits.can_use_exchange_channels:
        from app.exceptions import PlanFeatureError
        raise PlanFeatureError("Exchange channels require an upgraded plan")
    from app.repositories.channel import ChannelRepository
    count = await ChannelRepository(session, tenant.id).count()
    limits.check_capacity("channels", count)
    data = body.model_dump()
    data["tenant_id"] = tenant.id
    ch = await channel_service.create_channel(session, data, tenant_id=tenant.id)
    return ChannelResponse.from_channel(ch)


@router.get("/{id}", response_model=ChannelResponse)
async def get_channel(
    id: uuid.UUID,
    tenant: CurrentTenant,
    session: DBSession,
):
    ch = await channel_service.get_channel(session, id, tenant_id=tenant.id)
    return ChannelResponse.from_channel(ch)


@router.put("/{id}", response_model=ChannelResponse)
async def update_channel(
    id: uuid.UUID,
    body: ChannelUpdate,
    tenant: CurrentTenant,
    session: DBSession,
):
    data = body.model_dump(exclude_unset=True)
    ch = await channel_service.update_channel(session, id, data, tenant_id=tenant.id)
    return ChannelResponse.from_channel(ch)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_channel(
    id: uuid.UUID,
    tenant: CurrentTenant,
    session: DBSession,
):
    await channel_service.delete_channel(session, id, tenant_id=tenant.id)


@router.post("/{id}/test", response_model=ChannelTestResponse)
async def test_channel(
    id: uuid.UUID,
    tenant: CurrentTenant,
    session: DBSession,
):
    result = await channel_service.test_channel(session, id, tenant_id=tenant.id)
    return ChannelTestResponse(
        success=result.get("success", False),
        message=result.get("message", "Test failed."),
    )


@router.get("/{id}/health")
async def channel_health(
    id: uuid.UUID,
    tenant: CurrentTenant,
    session: DBSession,
):
    return await channel_service.check_channel_health(session, id, tenant_id=tenant.id)


@router.get("/{id}/deliveries", response_model=list[DeliveryResponse])
async def channel_deliveries(
    id: uuid.UUID,
    tenant: CurrentTenant,
    session: DBSession,
    pagination: PaginationParams = Depends(),
):
    await channel_service.get_channel(session, id, tenant_id=tenant.id)
    return await delivery_service.get_deliveries_for_channel(
        session,
        channel_id=id,
        tenant_id=tenant.id,
        limit=pagination.limit,
        offset=pagination.skip,
    )
