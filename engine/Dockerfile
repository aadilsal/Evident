# Evident engine image for the API and the worker (same image, different command).
# Build context is the repo root (deploy/docker-compose.yml): docker build -f engine/Dockerfile .
FROM python:3.12-slim AS base

# git for shallow clones; nothing else. Analysed repos are never built or run.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /usr/local/bin/uv

WORKDIR /app
COPY engine/pyproject.toml engine/uv.lock engine/README.md ./
COPY engine/src ./src
RUN uv sync --locked --no-dev --extra service \
    && useradd --system --uid 10001 --home /nonexistent evident

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    GIT_TERMINAL_PROMPT=0

USER evident
EXPOSE 8000
CMD ["uvicorn", "evident.service.api:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
