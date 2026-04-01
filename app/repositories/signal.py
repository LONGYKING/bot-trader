import uuid
from datetime import datetime

from sqlalchemy import and_, case, select, update

from app.models.signal import Signal
from app.repositories.base import BaseRepository


class SignalRepository(BaseRepository[Signal]):
    model = Signal

    async def get_latest_for_strategy(self, strategy_id: uuid.UUID) -> "Signal | None":
        stmt = (
            select(Signal)
            .where(Signal.strategy_id == strategy_id)
            .order_by(Signal.entry_time.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_strategy(
        self,
        strategy_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Signal]:
        stmt = (
            select(Signal)
            .where(Signal.strategy_id == strategy_id)
            .order_by(Signal.entry_time.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_filtered(
        self,
        strategy_id: uuid.UUID | None = None,
        asset: str | None = None,
        signal_value: int | None = None,
        from_dt: datetime | None = None,
        to_dt: datetime | None = None,
        is_profitable: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Signal]:
        stmt = select(Signal)
        conditions = []
        if strategy_id is not None:
            conditions.append(Signal.strategy_id == strategy_id)
        if asset is not None:
            conditions.append(Signal.asset == asset)
        if signal_value is not None:
            conditions.append(Signal.signal_value == signal_value)
        if from_dt is not None:
            conditions.append(Signal.entry_time >= from_dt)
        if to_dt is not None:
            conditions.append(Signal.entry_time <= to_dt)
        if is_profitable is not None:
            conditions.append(Signal.is_profitable == is_profitable)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        stmt = stmt.order_by(Signal.entry_time.desc()).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_filtered(
        self,
        strategy_id: uuid.UUID | None = None,
        asset: str | None = None,
        signal_value: int | None = None,
        from_dt: datetime | None = None,
        to_dt: datetime | None = None,
        is_profitable: bool | None = None,
    ) -> int:
        from sqlalchemy import func

        stmt = select(func.count()).select_from(Signal)
        conditions = []
        if strategy_id is not None:
            conditions.append(Signal.strategy_id == strategy_id)
        if asset is not None:
            conditions.append(Signal.asset == asset)
        if signal_value is not None:
            conditions.append(Signal.signal_value == signal_value)
        if from_dt is not None:
            conditions.append(Signal.entry_time >= from_dt)
        if to_dt is not None:
            conditions.append(Signal.entry_time <= to_dt)
        if is_profitable is not None:
            conditions.append(Signal.is_profitable == is_profitable)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_unresolved_expired(self, now: datetime) -> list[Signal]:
        stmt = (
            select(Signal)
            .where(
                and_(
                    Signal.expiry_time < now,
                    Signal.is_profitable.is_(None),
                )
            )
            .order_by(Signal.expiry_time)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def bulk_mark_profitable(
        self,
        ids: list[uuid.UUID],
        values: dict[uuid.UUID, bool],
    ) -> None:
        """Update is_profitable for multiple signals in a single statement."""
        if not ids:
            return
        stmt = (
            update(Signal)
            .where(Signal.id.in_(ids))
            .values(
                is_profitable=case(
                    *[(Signal.id == sid, val) for sid, val in values.items()],
                    else_=Signal.is_profitable,
                )
            )
        )
        await self.session.execute(stmt)
