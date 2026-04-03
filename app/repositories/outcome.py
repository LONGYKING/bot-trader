import uuid
from datetime import datetime

from sqlalchemy import and_, case, func, insert, select

from app.models.outcome import SignalOutcome
from app.models.signal import Signal
from app.repositories.base import BaseRepository


class OutcomeRepository(BaseRepository[SignalOutcome]):
    model = SignalOutcome

    async def get_by_signal(self, signal_id: uuid.UUID) -> SignalOutcome | None:
        stmt = select(SignalOutcome).where(SignalOutcome.signal_id == signal_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    def _outcome_conditions(
        self,
        is_profitable: bool | None = None,
        asset: str | None = None,
        strategy_id: uuid.UUID | None = None,
        from_dt: datetime | None = None,
        to_dt: datetime | None = None,
    ) -> list:
        conds = list(self._tenant_clause())
        if is_profitable is not None:
            conds.append(SignalOutcome.is_profitable == is_profitable)
        if from_dt is not None:
            conds.append(SignalOutcome.exit_time >= from_dt)
        if to_dt is not None:
            conds.append(SignalOutcome.exit_time <= to_dt)
        if asset is not None:
            conds.append(Signal.asset == asset)
        if strategy_id is not None:
            conds.append(Signal.strategy_id == strategy_id)
        return conds

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
            stmt = select(SignalOutcome).join(Signal, Signal.id == SignalOutcome.signal_id)
        else:
            stmt = select(SignalOutcome)

        conds = self._outcome_conditions(is_profitable, asset, strategy_id, from_dt, to_dt)
        if conds:
            stmt = stmt.where(and_(*conds))

        stmt = stmt.order_by(SignalOutcome.exit_time.desc()).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_stats(
        self,
        asset: str | None = None,
        strategy_id: uuid.UUID | None = None,
    ) -> dict:
        stmt = select(
            func.count(SignalOutcome.id).label("total_count"),
            func.sum(
                case((SignalOutcome.is_profitable == True, 1), else_=0)  # noqa: E712
            ).label("winning_count"),
            func.avg(SignalOutcome.pnl_pct).label("avg_pnl_pct"),
        )

        needs_signal_join = asset is not None or strategy_id is not None
        if needs_signal_join:
            stmt = stmt.join(Signal, Signal.id == SignalOutcome.signal_id)

        conds = self._outcome_conditions(asset=asset, strategy_id=strategy_id)
        if conds:
            stmt = stmt.where(and_(*conds))

        row = (await self.session.execute(stmt)).one()
        total_count = row.total_count or 0
        winning_count = row.winning_count or 0
        win_rate = (winning_count / total_count) if total_count > 0 else 0.0

        return {
            "total_count": total_count,
            "winning_count": winning_count,
            "win_rate": float(win_rate),
            "avg_pnl_pct": float(row.avg_pnl_pct) if row.avg_pnl_pct is not None else 0.0,
        }

    async def bulk_insert(self, outcomes: list[dict]) -> None:
        if not outcomes:
            return
        await self.session.execute(insert(SignalOutcome), outcomes)
