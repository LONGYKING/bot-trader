import uuid

from fastapi import APIRouter, Depends

from app.dependencies import DBSession, require_scope
from app.models.api_key import ApiKey
from app.repositories.api_key import ApiKeyRepository
from app.schemas.api_key import ApiKeyCreate, ApiKeyCreatedResponse, ApiKeyResponse, WorkerStats
from app.services import api_key_service

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/api-keys", response_model=list[ApiKeyResponse])
async def list_api_keys(
    session: DBSession,
    _: ApiKey = Depends(require_scope("admin")),
):
    repo = ApiKeyRepository(session)
    keys = await repo.list(limit=200)
    return keys


@router.post("/api-keys", response_model=ApiKeyCreatedResponse, status_code=201)
async def create_api_key(
    body: ApiKeyCreate,
    session: DBSession,
    _: ApiKey = Depends(require_scope("admin")),
):
    api_key, raw_key = await api_key_service.create_api_key(
        session, body.name, body.scopes, body.expires_at
    )
    return ApiKeyCreatedResponse(**ApiKeyResponse.model_validate(api_key).model_dump(), raw_key=raw_key)


@router.delete("/api-keys/{id}", status_code=204)
async def revoke_api_key(
    id: uuid.UUID,
    session: DBSession,
    _: ApiKey = Depends(require_scope("admin")),
):
    await api_key_service.revoke_api_key(session, id)


@router.post("/api-keys/{id}/rotate", response_model=ApiKeyCreatedResponse)
async def rotate_api_key(
    id: uuid.UUID,
    session: DBSession,
    _: ApiKey = Depends(require_scope("admin")),
):
    api_key, raw_key = await api_key_service.rotate_api_key(session, id)
    return ApiKeyCreatedResponse(**ApiKeyResponse.model_validate(api_key).model_dump(), raw_key=raw_key)


@router.get("/workers/stats", response_model=WorkerStats)
async def worker_stats(_: ApiKey = Depends(require_scope("admin"))):
    return WorkerStats(status="ok", message="Worker stats not yet implemented")
