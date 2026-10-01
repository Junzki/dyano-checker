# syntax=docker/dockerfile:1

FROM python:3.14-slim AS base

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install uv (static binaries from the official uv image)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install dependencies first for better layer caching.
# Build context is the repo root (see docker-compose.yaml).
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen

# Copy application source.
COPY backend ./backend

# Repo-level skill/gate/template defaults (fallback when a rule set has no
# uploaded skill files).
COPY skills ./skills

# docker CLI so the worker can spawn the checking agent container.
COPY --from=docker:cli /usr/local/bin/docker /usr/local/bin/docker

# Entrypoint used to run migrations + collectstatic before the real command.
COPY backend/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENV PATH="/opt/venv/bin:$PATH"
WORKDIR /app/backend

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["uvicorn", "config.asgi:application", "--host", "0.0.0.0", "--port", "8000"]
