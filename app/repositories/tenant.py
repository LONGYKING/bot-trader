from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant import Tenant, User
from app.repositories.base import BaseRepository


class TenantRepository(BaseRepository[Tenant]):
    model = Tenant

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, tenant_id=None)  # tenants are global

    async def get_by_name(self, name: str) -> Tenant | None:
        stmt = select(Tenant).where(Tenant.name == name)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_provider_customer(
        self, provider: str, provider_customer_id: str
    ) -> Tenant | None:
        stmt = select(Tenant).where(
            Tenant.payment_provider == provider,
            Tenant.provider_customer_id == provider_customer_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update(self, tenant_id: uuid.UUID, data: dict[str, Any]) -> Tenant | None:
        return await super().update(tenant_id, data)


class UserRepository(BaseRepository[User]):
    model = User

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, tenant_id=None)  # user lookups cross-tenant for auth

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_tenant(self, tenant_id: uuid.UUID) -> list[User]:
        stmt = select(User).where(User.tenant_id == tenant_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
