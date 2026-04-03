import uuid
from datetime import UTC, datetime

from sqlalchemy import and_, select, update
from sqlalchemy.sql.elements import ColumnElement

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
            .where(*self._tenant_clause(), SignalDelivery.channel_id == channel_id)
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

    async def get_by_signal_and_status(
        self, signal_id: uuid.UUID, status: str
    ) -> list[SignalDelivery]:
        stmt = select(SignalDelivery).where(
            SignalDelivery.signal_id == signal_id,
            SignalDelivery.status == status,
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def _update_status(
        self,
        id: uuid.UUID,
        new_status: str,
        status_clause: ColumnElement[bool],
        **extra_values: object,
    ) -> None:
        now = datetime.now(UTC)
        stmt = (
            update(SignalDelivery)
            .where(SignalDelivery.id == id, status_clause)
            .values(
                status=new_status,
                last_attempt_at=now,
                attempt_count=SignalDelivery.attempt_count + 1,
                **extra_values,
            )
        )
        await self.session.execute(stmt)

    async def mark_sent(
        self,
        id: uuid.UUID,
        external_msg_id: str | None = None,
        delivery_metadata: dict | None = None,
    ) -> None:
        now = datetime.now(UTC)
        await self._update_status(
            id,
            "sent",
            SignalDelivery.status.in_(["pending", "retrying"]),
            delivered_at=now,
            external_msg_id=external_msg_id,
            delivery_metadata=delivery_metadata,
            error_message=None,
        )

    async def mark_failed(self, id: uuid.UUID, error: str) -> None:
        await self._update_status(
            id,
            "failed",
            SignalDelivery.status == "pending",
            error_message=error,
        )

    async def mark_retrying(self, id: uuid.UUID, error: str) -> None:
        await self._update_status(
            id,
            "retrying",
            SignalDelivery.status.in_(["pending", "retrying"]),
            error_message=error,
        )

    async def mark_dlq(self, id: uuid.UUID, error: str) -> None:
        await self._update_status(
            id,
            "dlq",
            SignalDelivery.status != "dlq",
            error_message=error,
        )
