import uuid
from datetime import datetime

from sqlalchemy import and_, func, insert, select

from app.models.outcome import SignalOutcome
from app.models.signal import Signal
from app.repositories.base import BaseRepository


class OutcomeRepository(BaseRepository[SignalOutcome]):
    model = SignalOutcome

    async def get_by_signal(self, signal_id: uuid.UUID) -> SignalOutcome | None:
        stmt = select(SignalOutcome).where(SignalOutcome.signal_id == signal_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_filtered(
        self,
        is_profitable: bool | None = None,
        asset: str | None = None,
        strategy_id: uuid.UUID | None = None,
        from_dt: datetime | None = None,
        to_dt: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[SignalOutcome]:
        needs_signal_join = asset is not None or strategy_id is not None
        if needs_signal_join:
            stmt = select(SignalOutcome).join(
                Signal, Signal.id == SignalOutcome.signal_id
            )
        else:
            stmt = select(SignalOutcome)

        conditions = []
        if is_profitable is not None:
            conditions.append(SignalOutcome.is_profitable == is_profitable)
        if from_dt is not None:
            conditions.append(SignalOutcome.exit_time >= from_dt)
        if to_dt is not None:
            conditions.append(SignalOutcome.exit_time <= to_dt)
        if asset is not None:
            conditions.append(Signal.asset == asset)
        if strategy_id is not None:
            conditions.append(Signal.strategy_id == strategy_id)

        if conditions:
            stmt = stmt.where(and_(*conditions))

        stmt = stmt.order_by(SignalOutcome.exit_time.desc()).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_stats(
        self,
        asset: str | None = None,
        strategy_id: uuid.UUID | None = None,
    ) -> dict:
        needs_signal_join = asset is not None or strategy_id is not None
        if needs_signal_join:
            stmt = (
                select(
                    func.count(SignalOutcome.id).label("total_count"),
                    func.sum(
                        func.cast(SignalOutcome.is_profitable, type_=func.count().type)
                    ).label("winning_count_raw"),
                    func.avg(SignalOutcome.pnl_pct).label("avg_pnl_pct"),
                )
                .join(Signal, Signal.id == SignalOutcome.signal_id)
            )
        else:
            stmt = select(
                func.count(SignalOutcome.id).label("total_count"),
                func.avg(SignalOutcome.pnl_pct).label("avg_pnl_pct"),
            )

        conditions = []
        if asset is not None:
            conditions.append(Signal.asset == asset)
        if strategy_id is not None:
            conditions.append(Signal.strategy_id == strategy_id)
        if conditions:
            stmt = stmt.where(and_(*conditions))

        # Use a simpler approach with two separate queries for clarity and correctness
        count_stmt = select(func.count(SignalOutcome.id).label("total"))
        win_stmt = select(func.count(SignalOutcome.id).label("wins")).where(
            SignalOutcome.is_profitable == True  # noqa: E712
        )
        avg_stmt = select(func.avg(SignalOutcome.pnl_pct).label("avg_pnl"))

        base_conditions = []
        if asset is not None or strategy_id is not None:
            count_stmt = count_stmt.join(Signal, Signal.id == SignalOutcome.signal_id)
            win_stmt = win_stmt.join(Signal, Signal.id == SignalOutcome.signal_id)
            avg_stmt = avg_stmt.join(Signal, Signal.id == SignalOutcome.signal_id)

        if asset is not None:
            base_conditions.append(Signal.asset == asset)
        if strategy_id is not None:
            base_conditions.append(Signal.strategy_id == strategy_id)

        if base_conditions:
            count_stmt = count_stmt.where(and_(*base_conditions))
            win_stmt = win_stmt.where(and_(*base_conditions))
            avg_stmt = avg_stmt.where(and_(*base_conditions))

        total_result = await self.session.execute(count_stmt)
        total_count = total_result.scalar_one()

        win_result = await self.session.execute(win_stmt)
        winning_count = win_result.scalar_one()

        avg_result = await self.session.execute(avg_stmt)
        avg_pnl_pct = avg_result.scalar_one()

        win_rate = (winning_count / total_count) if total_count > 0 else 0.0

        return {
            "total_count": total_count,
            "winning_count": winning_count,
            "win_rate": float(win_rate),
            "avg_pnl_pct": float(avg_pnl_pct) if avg_pnl_pct is not None else 0.0,
        }

    async def bulk_insert(self, outcomes: list[dict]) -> None:
        if not outcomes:
            return
        await self.session.execute(insert(SignalOutcome), outcomes)
