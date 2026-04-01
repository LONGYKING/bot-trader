import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import NotFoundError
from app.models.delivery import SignalDelivery
from app.repositories.delivery import DeliveryRepository
from app.repositories.signal import SignalRepository
from app.repositories.subscription import SubscriptionRepository


async def fan_out_signal(
    session: AsyncSession,
    signal_id: uuid.UUID,
) -> int:
    """Find matching subscriptions and create pending delivery records.

    Pure data creation — no job enqueueing. Callers are responsible for
    dispatching the deliver_signal job after this returns.

    Returns the count of delivery records created.
    """
    signal_repo = SignalRepository(session)
    signal = await signal_repo.get_by_id(signal_id)
    if signal is None:
        raise NotFoundError("Signal", str(signal_id))

    sub_repo = SubscriptionRepository(session)
    matches = await sub_repo.get_matching_for_signal(signal)

    if not matches:
        return 0

    delivery_repo = DeliveryRepository(session)
    now = datetime.now(UTC)
    created_count = 0

    for subscription, channel in matches:
        await delivery_repo.create(
            {
                "signal_id": signal_id,
                "subscription_id": subscription.id,
                "channel_id": channel.id,
                "status": "pending",
                "attempt_count": 0,
                "created_at": now,
            }
        )
        created_count += 1

    return created_count


async def get_deliveries_for_signal(
    session: AsyncSession,
    signal_id: uuid.UUID,
) -> list[SignalDelivery]:
    """Return all delivery records for a signal."""
    repo = DeliveryRepository(session)
    return await repo.get_by_signal(signal_id)


async def get_deliveries_for_channel(
    session: AsyncSession,
    channel_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
) -> list[SignalDelivery]:
    """Return paginated delivery records for a channel."""
    repo = DeliveryRepository(session)
    return await repo.get_by_channel(channel_id, limit=limit, offset=offset)
