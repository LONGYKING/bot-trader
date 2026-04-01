import uuid
from datetime import UTC, datetime

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

    async def get_pending_retries(self, max_attempts: int) -> list[SignalDelivery]:
        stmt = (
            select(SignalDelivery)
            .where(
                and_(
                    SignalDelivery.status.in_(["pending", "retrying"]),
                    SignalDelivery.attempt_count < max_attempts,
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
        delivery_metadata: dict | None = None,
    ) -> None:
        now = datetime.now(UTC)
        stmt = (
            update(SignalDelivery)
            .where(
                SignalDelivery.id == id,
                SignalDelivery.status.in_(["pending", "retrying"]),
            )
            .values(
                status="sent",
                delivered_at=now,
                last_attempt_at=now,
                attempt_count=SignalDelivery.attempt_count + 1,
                external_msg_id=external_msg_id,
                delivery_metadata=delivery_metadata,
                error_message=None,
            )
        )
        await self.session.execute(stmt)

    async def mark_failed(self, id: uuid.UUID, error: str) -> None:
        now = datetime.now(UTC)
        stmt = (
            update(SignalDelivery)
            .where(
                SignalDelivery.id == id,
                SignalDelivery.status == "pending",
            )
            .values(
                status="failed",
                last_attempt_at=now,
                attempt_count=SignalDelivery.attempt_count + 1,
                error_message=error,
            )
        )
        await self.session.execute(stmt)

    async def mark_retrying(self, id: uuid.UUID, error: str) -> None:
        now = datetime.now(UTC)
        stmt = (
            update(SignalDelivery)
            .where(
                SignalDelivery.id == id,
                SignalDelivery.status.in_(["pending", "retrying"]),
            )
            .values(
                status="retrying",
                last_attempt_at=now,
                attempt_count=SignalDelivery.attempt_count + 1,
                error_message=error,
            )
        )
        await self.session.execute(stmt)

    async def mark_dlq(self, id: uuid.UUID, error: str) -> None:
        now = datetime.now(UTC)
        stmt = (
            update(SignalDelivery)
            .where(
                SignalDelivery.id == id,
                SignalDelivery.status != "dlq",
            )
            .values(
                status="dlq",
                last_attempt_at=now,
                attempt_count=SignalDelivery.attempt_count + 1,
                error_message=error,
            )
        )
        await self.session.execute(stmt)
