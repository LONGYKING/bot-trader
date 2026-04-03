import uuid
from typing import Any, Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    model: type[ModelT]

    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID | None = None) -> None:
        self.session = session
        self.tenant_id = tenant_id  # None = global access (workers, admin)

    def _tenant_clause(self) -> list:
        """Return a WHERE clause filtering by tenant_id, or [] for global access."""
        if self.tenant_id is None:
            return []
        if not hasattr(self.model, "tenant_id"):
            return []
        return [self.model.tenant_id == self.tenant_id]  # type: ignore[attr-defined]

    async def get_by_id(self, id: uuid.UUID) -> ModelT | None:
        stmt = select(self.model).where(
            self.model.id == id,  # type: ignore[attr-defined]
            *self._tenant_clause(),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list(
        self,
        skip: int = 0,
        limit: int = 50,
        **filters: Any,
    ) -> list[ModelT]:
        stmt = select(self.model).where(*self._tenant_clause())
        for key, value in filters.items():
            if hasattr(self.model, key) and value is not None:
                stmt = stmt.where(getattr(self.model, key) == value)
        stmt = stmt.offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count(self, **filters: Any) -> int:
        stmt = select(func.count()).select_from(self.model).where(*self._tenant_clause())
        for key, value in filters.items():
            if hasattr(self.model, key) and value is not None:
                stmt = stmt.where(getattr(self.model, key) == value)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def create(self, data: dict[str, Any]) -> ModelT:
        if self.tenant_id is not None and hasattr(self.model, "tenant_id"):
            data.setdefault("tenant_id", self.tenant_id)
        instance = self.model(**data)
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def update(self, id: uuid.UUID, data: dict[str, Any]) -> ModelT | None:
        instance = await self.get_by_id(id)
        if instance is None:
            return None
        for key, value in data.items():
            if hasattr(instance, key):
                setattr(instance, key, value)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def delete(self, id: uuid.UUID) -> bool:
        instance = await self.get_by_id(id)
        if instance is None:
            return False
        await self.session.delete(instance)
        await self.session.flush()
        return True

    async def exists(self, id: uuid.UUID) -> bool:
        return await self.get_by_id(id) is not None
