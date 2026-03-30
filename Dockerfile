# ---- builder ----
FROM python:3.12-slim AS builder
WORKDIR /app

# Install uv
RUN pip install uv

COPY pyproject.toml ./
# Copy lock file if it exists (optional — uv will resolve if absent)
COPY uv.lock* ./

# Install deps into .venv (no lock file = resolve fresh; lock file = use it)
RUN uv sync --no-dev --no-install-project || uv sync --no-dev --no-install-project --no-cache

COPY . .
RUN uv sync --no-dev

# ---- runtime ----
FROM python:3.12-slim AS runtime
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

# Copy venv and app from builder
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app /app

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
