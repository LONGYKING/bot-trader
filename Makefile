.PHONY: dev worker migrate migration test lint format seed-api-key \
        docker-up docker-down docker-build docker-logs docker-api docker-worker \
        install setup

# ── Local development ──────────────────────────────────────────────────────────

install:
	uv sync

# Start Postgres + Redis only (for local dev)
setup:
	docker-compose up -d postgres redis
	@echo "Waiting for Postgres..."
	@sleep 3
	$(MAKE) migrate

dev:
	uv run uvicorn app.main:app --reload --port 8000

worker:
	uv run python -m arq app.workers.settings.WorkerSettings

migrate:
	uv run alembic upgrade head

migration:
	uv run alembic revision --autogenerate -m "$(name)"

test:
	uv run pytest tests/ -v --cov=app --cov-report=term-missing

lint:
	uv run ruff check app/ tests/
	uv run ruff format --check app/ tests/

format:
	uv run ruff format app/ tests/
	uv run ruff check --fix app/ tests/

seed-api-key:
	uv run python scripts/create_api_key.py

# ── Docker (full stack) ────────────────────────────────────────────────────────

docker-build:
	docker-compose build

# Start full stack: postgres, redis, migrate, api, worker
docker-up:
	docker-compose up -d

# Tail logs for api + worker
docker-logs:
	docker-compose logs -f api worker

docker-api:
	docker-compose up -d api

docker-worker:
	docker-compose up -d worker

docker-down:
	docker-compose down

# Remove containers AND volumes (wipes DB)
docker-clean:
	docker-compose down -v
