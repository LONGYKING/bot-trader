from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant import Plan, TenantOverride
from app.repositories.base import BaseRepository


class PlanRepository(BaseRepository[Plan]):
    model = Plan

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, tenant_id=None)  # plans are global

    async def get_by_key(self, key: str) -> Plan | None:
        stmt = select(Plan).where(Plan.key == key)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_active(self) -> list[Plan]:
        stmt = select(Plan).where(Plan.is_active == True).order_by(Plan.sort_order)  # noqa: E712
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_public(self) -> list[Plan]:
        stmt = (
            select(Plan)
            .where(Plan.is_active == True, Plan.is_public == True)  # noqa: E712
            .order_by(Plan.sort_order)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_all(self) -> list[Plan]:
        stmt = select(Plan).order_by(Plan.sort_order)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_by_key(self, key: str, data: dict[str, Any]) -> Plan | None:
        plan = await self.get_by_key(key)
        if plan is None:
            return None
        for field, value in data.items():
            if hasattr(plan, field):
                setattr(plan, field, value)
        await self.session.flush()
        await self.session.refresh(plan)
        return plan

    async def delete_by_key(self, key: str) -> bool:
        plan = await self.get_by_key(key)
        if plan is None:
            return False
        await self.session.delete(plan)
        await self.session.flush()
        return True


class OverrideRepository(BaseRepository[TenantOverride]):
    model = TenantOverride

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, tenant_id=None)

    async def get_by_tenant(self, tenant_id: uuid.UUID) -> TenantOverride | None:
        stmt = select(TenantOverride).where(TenantOverride.tenant_id == tenant_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert(self, tenant_id: uuid.UUID, data: dict[str, Any]) -> TenantOverride:
        override = await self.get_by_tenant(tenant_id)
        if override is None:
            override = TenantOverride(tenant_id=tenant_id, **data)
            self.session.add(override)
        else:
            for field, value in data.items():
                if hasattr(override, field):
                    setattr(override, field, value)
        await self.session.flush()
        await self.session.refresh(override)
        return override

    async def delete_by_tenant(self, tenant_id: uuid.UUID) -> bool:
        override = await self.get_by_tenant(tenant_id)
        if override is None:
            return False
        await self.session.delete(override)
        await self.session.flush()
        return True
