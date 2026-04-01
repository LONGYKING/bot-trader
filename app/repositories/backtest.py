import uuid
from datetime import UTC, datetime

from sqlalchemy import insert, select, update

from app.models.backtest import Backtest, BacktestTrade
from app.repositories.base import BaseRepository


class BacktestRepository(BaseRepository[Backtest]):
    model = Backtest

    async def get_by_strategy(self, strategy_id: uuid.UUID) -> list[Backtest]:
        stmt = (
            select(Backtest)
            .where(Backtest.strategy_id == strategy_id)
            .order_by(Backtest.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def set_running(self, id: uuid.UUID, arq_job_id: str) -> None:
        stmt = (
            update(Backtest)
            .where(Backtest.id == id)
            .values(
                status="running",
                arq_job_id=arq_job_id,
                started_at=datetime.now(UTC),
            )
        )
        await self.session.execute(stmt)

    async def set_completed(self, id: uuid.UUID, results: dict) -> None:
        stmt = (
            update(Backtest)
            .where(Backtest.id == id)
            .values(
                status="completed",
                completed_at=datetime.now(UTC),
                total_trades=results.get("total_trades"),
                winning_trades=results.get("winning_trades"),
                win_rate=results.get("win_rate"),
                total_pnl_pct=results.get("total_pnl_pct"),
                sharpe_ratio=results.get("sharpe_ratio"),
                max_drawdown_pct=results.get("max_drawdown_pct"),
                annual_return_pct=results.get("annual_return_pct"),
                sheets_url=results.get("sheets_url"),
            )
        )
        await self.session.execute(stmt)

    async def set_failed(self, id: uuid.UUID, error: str) -> None:
        stmt = (
            update(Backtest)
            .where(Backtest.id == id)
            .values(
                status="failed",
                completed_at=datetime.now(UTC),
                error_message=error,
            )
        )
        await self.session.execute(stmt)

    async def get_trades(
        self,
        backtest_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[BacktestTrade]:
        stmt = (
            select(BacktestTrade)
            .where(BacktestTrade.backtest_id == backtest_id)
            .order_by(BacktestTrade.entry_time)
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_trades(self, backtest_id: uuid.UUID) -> int:
        from sqlalchemy import func

        stmt = (
            select(func.count())
            .select_from(BacktestTrade)
            .where(BacktestTrade.backtest_id == backtest_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def bulk_insert_trades(self, trades: list[dict]) -> None:
        if not trades:
            return
        await self.session.execute(insert(BacktestTrade), trades)

    async def get_equity_curve(self, backtest_id: uuid.UUID) -> list[dict]:
        stmt = (
            select(
                BacktestTrade.entry_time,
                BacktestTrade.exit_time,
                BacktestTrade.pnl_pct,
            )
            .where(BacktestTrade.backtest_id == backtest_id)
            .order_by(BacktestTrade.entry_time)
        )
        result = await self.session.execute(stmt)
        rows = result.all()
        return [
            {
                "entry_time": row.entry_time,
                "exit_time": row.exit_time,
                "pnl_pct": float(row.pnl_pct),
            }
            for row in rows
        ]
