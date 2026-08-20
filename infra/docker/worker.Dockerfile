# See api.Dockerfile for why this is multi-stage and --no-editable.
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.11.29 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

WORKDIR /repo

COPY pyproject.toml uv.lock ./
COPY libs/core ./libs/core
COPY services/api ./services/api
COPY services/worker ./services/worker

RUN uv sync --frozen --no-dev --no-editable --package worker

FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/repo/.venv/bin:$PATH"

RUN groupadd --gid 10001 appuser \
    && useradd --uid 10001 --gid appuser --no-create-home --shell /usr/sbin/nologin appuser

WORKDIR /repo
COPY --from=builder --chown=appuser:appuser /repo/.venv /repo/.venv

USER appuser

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD celery -A worker.celery_app.celery_app inspect ping -t 5 || exit 1

CMD ["celery", "-A", "worker.celery_app.celery_app", "worker", "--loglevel=INFO"]
