from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.exceptions import AuthenticationError, ConflictError
from app.models.tenant import Tenant, User
from app.repositories.tenant import TenantRepository, UserRepository


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def encode_access_token(user: User, tenant: Tenant) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user.id),
        "tenant_id": str(tenant.id),
        "email": user.email,
        "plan_key": tenant.plan_key,
        "is_owner": user.is_owner,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_access_expires_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def encode_refresh_token(user: User) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user.id),
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=settings.jwt_refresh_expires_days),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        raise AuthenticationError("Invalid or expired token")


async def register(
    session: AsyncSession,
    email: str,
    password: str,
    full_name: str | None = None,
) -> tuple[str, str]:
    """
    Create a new Tenant + owner User. Returns (access_token, refresh_token).
    """
    user_repo = UserRepository(session)
    tenant_repo = TenantRepository(session)

    existing = await user_repo.get_by_email(email)
    if existing:
        raise ConflictError(f"An account with email '{email}' already exists")

    # Derive a workspace name from the email prefix
    workspace_name = email.split("@")[0].lower().replace(".", "_").replace("+", "_")
    base_name = workspace_name
    counter = 1
    while await tenant_repo.get_by_name(workspace_name):
        workspace_name = f"{base_name}_{counter}"
        counter += 1

    tenant = await tenant_repo.create({"name": workspace_name, "plan_key": "free"})
    user = await user_repo.create(
        {
            "tenant_id": tenant.id,
            "email": email,
            "password_hash": _hash_password(password),
            "full_name": full_name,
            "is_owner": True,
        }
    )

    return encode_access_token(user, tenant), encode_refresh_token(user)


async def login(
    session: AsyncSession,
    email: str,
    password: str,
) -> tuple[str, str]:
    """Returns (access_token, refresh_token) or raises AuthenticationError."""
    user_repo = UserRepository(session)
    tenant_repo = TenantRepository(session)

    user = await user_repo.get_by_email(email)
    if not user or not _verify_password(password, user.password_hash):
        raise AuthenticationError("Invalid email or password")

    tenant = await tenant_repo.get_by_id(user.tenant_id)
    if not tenant:
        raise AuthenticationError("Tenant not found for this user")

    return encode_access_token(user, tenant), encode_refresh_token(user)


async def refresh(
    session: AsyncSession,
    refresh_token: str,
) -> tuple[str, str]:
    """Validate refresh token and return a fresh token pair."""
    payload = decode_token(refresh_token)
    if payload.get("type") != "refresh":
        raise AuthenticationError("Not a refresh token")

    user_repo = UserRepository(session)
    tenant_repo = TenantRepository(session)

    user_id = uuid.UUID(payload["sub"])
    user = await user_repo.get_by_id(user_id)
    if not user:
        raise AuthenticationError("User not found")

    tenant = await tenant_repo.get_by_id(user.tenant_id)
    if not tenant:
        raise AuthenticationError("Tenant not found")

    return encode_access_token(user, tenant), encode_refresh_token(user)
