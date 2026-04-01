import uuid

from fastapi import APIRouter, Depends, status

from app.dependencies import DBSession, PaginationParams, require_scope
from app.models.api_key import ApiKey
from app.schemas.channel import ChannelCreate, ChannelResponse, ChannelTestResponse, ChannelUpdate
from app.schemas.delivery import DeliveryResponse
from app.services import channel_service, delivery_service

router = APIRouter(prefix="/channels")


@router.get("", response_model=list[ChannelResponse])
async def list_channels(
    session: DBSession,
    _: ApiKey = Depends(require_scope("admin")),
    pagination: PaginationParams = Depends(),
):
    """List active channels. Paginated — default page size 100."""
    return await channel_service.list_channels(
        session, limit=pagination.limit, offset=pagination.skip
    )


@router.post("", response_model=ChannelResponse, status_code=status.HTTP_201_CREATED)
async def create_channel(
    body: ChannelCreate,
    session: DBSession,
    _: ApiKey = Depends(require_scope("admin")),
):
    """Create a new notification channel."""
    return await channel_service.create_channel(session, body.model_dump())


@router.get("/{id}", response_model=ChannelResponse)
async def get_channel(
    id: uuid.UUID,
    session: DBSession,
    _: ApiKey = Depends(require_scope("admin")),
):
    """Get a channel by id. Config (credentials) is masked in the response."""
    return await channel_service.get_channel(session, id)


@router.put("/{id}", response_model=ChannelResponse)
async def update_channel(
    id: uuid.UUID,
    body: ChannelUpdate,
    session: DBSession,
    _: ApiKey = Depends(require_scope("admin")),
):
    """Update a channel's configuration."""
    data = body.model_dump(exclude_unset=True)
    return await channel_service.update_channel(session, id, data)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_channel(
    id: uuid.UUID,
    session: DBSession,
    _: ApiKey = Depends(require_scope("admin")),
):
    """Delete a channel. Cascade removes associated subscriptions and deliveries."""
    await channel_service.delete_channel(session, id)


@router.post("/{id}/test", response_model=ChannelTestResponse)
async def test_channel(
    id: uuid.UUID,
    session: DBSession,
    _: ApiKey = Depends(require_scope("admin")),
):
    """Send a test message through the channel."""
    result = await channel_service.test_channel(session, id)
    return ChannelTestResponse(
        success=result.get("success", False),
        message=result.get("message", "Test failed."),
    )


@router.get("/{id}/health")
async def channel_health(
    id: uuid.UUID,
    session: DBSession,
    _: ApiKey = Depends(require_scope("admin")),
):
    """Run a live health check on the channel and persist the result."""
    return await channel_service.check_channel_health(session, id)


@router.get("/{id}/deliveries", response_model=list[DeliveryResponse])
async def channel_deliveries(
    id: uuid.UUID,
    session: DBSession,
    _: ApiKey = Depends(require_scope("admin")),
    pagination: PaginationParams = Depends(),
):
    """Return delivery history for a channel."""
    # Ensure channel exists
    await channel_service.get_channel(session, id)
    return await delivery_service.get_deliveries_for_channel(
        session,
        channel_id=id,
        limit=pagination.limit,
        offset=pagination.skip,
    )
