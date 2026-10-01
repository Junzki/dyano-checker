# syntax=docker/dockerfile:1

# Python 3.12 is used (not the backend's 3.14) because PaddleOCR/PaddlePaddle
# do not ship Python 3.14 wheels yet.
FROM python:3.12-slim

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml ./
# No committed uv.lock (PaddlePaddle wheels are huge/volatile); resolve at build.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync

COPY src ./src

ENV PATH="/opt/venv/bin:$PATH"

ENTRYPOINT ["python", "-m", "dyano_agent"]
