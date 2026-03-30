import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import require_scope
from app.exceptions import NotFoundError
from app.models.api_key import ApiKey
from app.repositories.api_key import ApiKeyRepository
from app.services import api_key_service

router = APIRouter(prefix="/admin", tags=["Admin"])


class ApiKeyCreate(BaseModel):
    name: str
    scopes: list[str] = ["read:signals"]
    expires_at: datetime | None = None


class ApiKeyRead(BaseModel):
    id: uuid.UUID
    name: str
    key_prefix: str
    scopes: list[str]
    is_active: bool
    last_used_at: datetime | None
    expires_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ApiKeyCreated(ApiKeyRead):
    key: str  # raw key shown once


class WorkerStats(BaseModel):
    status: str
    message: str


@router.get("/api-keys", response_model=list[ApiKeyRead])
async def list_api_keys(
    session: AsyncSession = Depends(get_db),
    _: ApiKey = Depends(require_scope("admin")),
):
    repo = ApiKeyRepository(session)
    keys = await repo.list(limit=200)
    return keys


@router.post("/api-keys", response_model=ApiKeyCreated, status_code=201)
async def create_api_key(
    body: ApiKeyCreate,
    session: AsyncSession = Depends(get_db),
    _: ApiKey = Depends(require_scope("admin")),
):
    api_key, raw_key = await api_key_service.create_api_key(
        session, body.name, body.scopes, body.expires_at
    )
    return ApiKeyCreated(**ApiKeyRead.model_validate(api_key).model_dump(), key=raw_key)


@router.delete("/api-keys/{id}", status_code=204)
async def revoke_api_key(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    _: ApiKey = Depends(require_scope("admin")),
):
    await api_key_service.revoke_api_key(session, id)


@router.post("/api-keys/{id}/rotate", response_model=ApiKeyCreated)
async def rotate_api_key(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    _: ApiKey = Depends(require_scope("admin")),
):
    api_key, raw_key = await api_key_service.rotate_api_key(session, id)
    return ApiKeyCreated(**ApiKeyRead.model_validate(api_key).model_dump(), key=raw_key)


@router.get("/workers/stats", response_model=WorkerStats)
async def worker_stats(_: ApiKey = Depends(require_scope("admin"))):
    return WorkerStats(status="ok", message="Worker stats not yet implemented")
