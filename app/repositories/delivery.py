import uuid
from datetime import datetime, timezone

from sqlalchemy import and_, select, update

from app.models.delivery import SignalDelivery
from app.repositories.base import BaseRepository


class DeliveryRepository(BaseRepository[SignalDelivery]):
    model = SignalDelivery

    async def get_by_signal(self, signal_id: uuid.UUID) -> list[SignalDelivery]:
        stmt = (
            select(SignalDelivery)
            .where(SignalDelivery.signal_id == signal_id)
            .order_by(SignalDelivery.created_at)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_channel(
        self,
        channel_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[SignalDelivery]:
        stmt = (
            select(SignalDelivery)
            .where(SignalDelivery.channel_id == channel_id)
            .order_by(SignalDelivery.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_pending_retries(self) -> list[SignalDelivery]:
        stmt = (
            select(SignalDelivery)
            .where(
                and_(
                    SignalDelivery.status.in_(["pending", "retrying"]),
                    SignalDelivery.attempt_count < 5,
                )
            )
            .order_by(SignalDelivery.created_at)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def mark_sent(
        self,
        id: uuid.UUID,
        external_msg_id: str | None = None,
    ) -> None:
        now = datetime.now(timezone.utc)
        stmt = (
            update(SignalDelivery)
            .where(SignalDelivery.id == id)
            .values(
                status="sent",
                delivered_at=now,
                last_attempt_at=now,
                attempt_count=SignalDelivery.attempt_count + 1,
                external_msg_id=external_msg_id,
                error_message=None,
            )
        )
        await self.session.execute(stmt)

    async def mark_failed(self, id: uuid.UUID, error: str) -> None:
        now = datetime.now(timezone.utc)
        stmt = (
            update(SignalDelivery)
            .where(SignalDelivery.id == id)
            .values(
                status="failed",
                last_attempt_at=now,
                attempt_count=SignalDelivery.attempt_count + 1,
                error_message=error,
            )
        )
        await self.session.execute(stmt)

    async def mark_retrying(self, id: uuid.UUID, error: str) -> None:
        now = datetime.now(timezone.utc)
        stmt = (
            update(SignalDelivery)
            .where(SignalDelivery.id == id)
            .values(
                status="retrying",
                last_attempt_at=now,
                attempt_count=SignalDelivery.attempt_count + 1,
                error_message=error,
            )
        )
        await self.session.execute(stmt)

    async def mark_dlq(self, id: uuid.UUID, error: str) -> None:
        now = datetime.now(timezone.utc)
        stmt = (
            update(SignalDelivery)
            .where(SignalDelivery.id == id)
            .values(
                status="dlq",
                last_attempt_at=now,
                attempt_count=SignalDelivery.attempt_count + 1,
                error_message=error,
            )
        )
        await self.session.execute(stmt)
