import uuid

from sqlalchemy import and_, or_, select

from app.models.channel import Channel
from app.models.signal import Signal
from app.models.subscription import Subscription
from app.repositories.base import BaseRepository


class SubscriptionRepository(BaseRepository[Subscription]):
    model = Subscription

    async def get_matching_for_signal(
        self,
        signal: Signal,
    ) -> list[tuple[Subscription, Channel]]:
        """Return (Subscription, Channel) pairs whose filters match *signal*.

        Matching rules:
        - ``is_active`` must be True on both subscription and channel.
        - ``strategy_id`` IS NULL  OR  strategy_id == signal.strategy_id
        - ``asset_filter`` IS NULL  OR  signal.asset = ANY(asset_filter)
        - ``signal_filter`` IS NULL  OR  signal.signal_value = ANY(signal_filter)
        - ``min_confidence`` <= signal.confidence  (NULL confidence treated as 0)
        """
        from sqlalchemy import func, literal

        confidence = float(signal.confidence) if signal.confidence is not None else 0.0

        stmt = (
            select(Subscription, Channel)
            .join(Channel, Channel.id == Subscription.channel_id)
            .where(
                and_(
                    Subscription.is_active == True,  # noqa: E712
                    Channel.is_active == True,  # noqa: E712
                    or_(
                        Subscription.strategy_id.is_(None),
                        Subscription.strategy_id == signal.strategy_id,
                    ),
                    or_(
                        Subscription.asset_filter.is_(None),
                        literal(signal.asset) == func.any(Subscription.asset_filter),
                    ),
                    or_(
                        Subscription.signal_filter.is_(None),
                        literal(signal.signal_value) == func.any(Subscription.signal_filter),
                    ),
                    Subscription.min_confidence <= confidence,
                )
            )
        )
        result = await self.session.execute(stmt)
        return list(result.tuples().all())

    async def list_by_channel(self, channel_id: uuid.UUID) -> list[Subscription]:
        stmt = (
            select(Subscription)
            .where(*self._tenant_clause(), Subscription.channel_id == channel_id)
            .order_by(Subscription.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
