from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ConflictError, NotFoundError
from app.models.tenant import Plan, TenantOverride
from app.repositories.plan import OverrideRepository, PlanRepository


async def list_plans(session: AsyncSession, public_only: bool = False) -> list[Plan]:
    repo = PlanRepository(session)
    if public_only:
        return await repo.list_public()
    return await repo.list_all()


async def get_plan(session: AsyncSession, key: str) -> Plan:
    repo = PlanRepository(session)
    plan = await repo.get_by_key(key)
    if not plan:
        raise NotFoundError("Plan", key)
    return plan


async def create_plan(session: AsyncSession, data: dict[str, Any]) -> Plan:
    repo = PlanRepository(session)
    existing = await repo.get_by_key(data["key"])
    if existing:
        raise ConflictError(f"Plan with key '{data['key']}' already exists")
    return await repo.create(data)


async def update_plan(session: AsyncSession, key: str, data: dict[str, Any]) -> Plan:
    repo = PlanRepository(session)
    plan = await repo.update_by_key(key, data)
    if not plan:
        raise NotFoundError("Plan", key)
    return plan


async def delete_plan(session: AsyncSession, key: str) -> None:
    repo = PlanRepository(session)
    deleted = await repo.delete_by_key(key)
    if not deleted:
        raise NotFoundError("Plan", key)


async def set_tenant_override(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    data: dict[str, Any],
) -> TenantOverride:
    repo = OverrideRepository(session)
    return await repo.upsert(tenant_id, data)


async def remove_tenant_override(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    repo = OverrideRepository(session)
    deleted = await repo.delete_by_tenant(tenant_id)
    if not deleted:
        raise NotFoundError("TenantOverride", str(tenant_id))


async def get_tenant_override(
    session: AsyncSession, tenant_id: uuid.UUID
) -> TenantOverride | None:
    repo = OverrideRepository(session)
    return await repo.get_by_tenant(tenant_id)
