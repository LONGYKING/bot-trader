import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update

from app.models.api_key import ApiKey
from app.repositories.base import BaseRepository


class ApiKeyRepository(BaseRepository[ApiKey]):
    model = ApiKey

    async def get_by_hash(self, key_hash: str) -> ApiKey | None:
        stmt = select(ApiKey).where(ApiKey.key_hash == key_hash)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_last_used(self, id: uuid.UUID) -> None:
        stmt = (
            update(ApiKey)
            .where(ApiKey.id == id)
            .values(last_used_at=datetime.now(timezone.utc))
        )
        await self.session.execute(stmt)
