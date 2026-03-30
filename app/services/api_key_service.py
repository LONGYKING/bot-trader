import hashlib
import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import AuthenticationError, NotFoundError
from app.models.api_key import ApiKey
from app.repositories.api_key import ApiKeyRepository


def _generate_raw_key() -> str:
    """Generate a raw API key: sp_ prefix + 32 bytes of URL-safe base64."""
    return "sp_" + secrets.token_urlsafe(32)


def _hash_key(raw_key: str) -> str:
    """SHA-256 hex digest of the raw key."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


async def create_api_key(
    session: AsyncSession,
    name: str,
    scopes: list[str],
    expires_at: datetime | None = None,
) -> tuple[ApiKey, str]:
    """
    Create a new API key. Returns (ApiKey model, raw_key).
    The raw_key is returned ONCE — it is not stored.
    """
    raw_key = _generate_raw_key()
    key_hash = _hash_key(raw_key)
    key_prefix = raw_key[:10]  # "sp_" + 7 chars

    repo = ApiKeyRepository(session)
    api_key = await repo.create({
        "name": name,
        "key_hash": key_hash,
        "key_prefix": key_prefix,
        "scopes": scopes,
        "expires_at": expires_at,
    })
    return api_key, raw_key


async def get_api_key_by_raw(
    session: AsyncSession,
    raw_key: str,
) -> ApiKey | None:
    """Lookup ApiKey by raw key (hashes internally)."""
    key_hash = _hash_key(raw_key)
    repo = ApiKeyRepository(session)
    return await repo.get_by_hash(key_hash)


async def authenticate(
    session: AsyncSession,
    raw_key: str,
) -> ApiKey:
    """
    Authenticate a raw API key. Returns ApiKey or raises AuthenticationError.
    Updates last_used_at on success.
    """
    now = datetime.now(timezone.utc)
    api_key = await get_api_key_by_raw(session, raw_key)

    if api_key is None:
        raise AuthenticationError()
    if not api_key.is_active:
        raise AuthenticationError("API key is inactive")
    if api_key.expires_at and api_key.expires_at.astimezone(timezone.utc) < now:
        raise AuthenticationError("API key has expired")

    repo = ApiKeyRepository(session)
    await repo.update_last_used(api_key.id)
    return api_key


async def rotate_api_key(
    session: AsyncSession,
    id: uuid.UUID,
) -> tuple[ApiKey, str]:
    """Replace key hash with a new one. Returns (model, new_raw_key)."""
    repo = ApiKeyRepository(session)
    api_key = await repo.get_by_id(id)
    if api_key is None:
        raise NotFoundError("ApiKey", str(id))

    new_raw_key = _generate_raw_key()
    new_hash = _hash_key(new_raw_key)
    new_prefix = new_raw_key[:10]

    updated = await repo.update(id, {"key_hash": new_hash, "key_prefix": new_prefix})
    return updated, new_raw_key


async def revoke_api_key(session: AsyncSession, id: uuid.UUID) -> None:
    """Set is_active = False."""
    repo = ApiKeyRepository(session)
    api_key = await repo.get_by_id(id)
    if api_key is None:
        raise NotFoundError("ApiKey", str(id))
    await repo.update(id, {"is_active": False})
