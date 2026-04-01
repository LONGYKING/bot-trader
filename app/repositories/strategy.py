import uuid

from sqlalchemy import select, update

from app.models.strategy import Strategy
from app.repositories.base import BaseRepository


class StrategyRepository(BaseRepository[Strategy]):
    model = Strategy

    async def get_by_ids(self, ids: list[uuid.UUID]) -> dict[uuid.UUID, Strategy]:
        """Batch-load strategies by id. Returns a {id: Strategy} map."""
        if not ids:
            return {}
        stmt = select(Strategy).where(Strategy.id.in_(ids))
        result = await self.session.execute(stmt)
        return {s.id: s for s in result.scalars().all()}

    async def get_by_name(self, name: str) -> Strategy | None:
        stmt = select(Strategy).where(Strategy.name == name)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_active(
        self,
        asset: str | None = None,
        timeframe: str | None = None,
        strategy_class: str | None = None,
    ) -> list[Strategy]:
        stmt = select(Strategy).where(Strategy.is_active == True)  # noqa: E712
        if asset is not None:
            stmt = stmt.where(Strategy.asset == asset)
        if timeframe is not None:
            stmt = stmt.where(Strategy.timeframe == timeframe)
        if strategy_class is not None:
            stmt = stmt.where(Strategy.strategy_class == strategy_class)
        stmt = stmt.order_by(Strategy.name)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def increment_version(self, id: uuid.UUID) -> None:
        stmt = (
            update(Strategy)
            .where(Strategy.id == id)
            .values(version=Strategy.version + 1)
        )
        await self.session.execute(stmt)
