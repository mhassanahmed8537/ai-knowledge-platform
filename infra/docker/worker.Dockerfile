FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.29 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

WORKDIR /repo

COPY pyproject.toml uv.lock ./
COPY libs/core ./libs/core
COPY services/api ./services/api
COPY services/worker ./services/worker

RUN uv sync --frozen --package worker --no-dev

WORKDIR /repo/services/worker

CMD ["uv", "run", "--frozen", "--no-dev", "--project", "/repo", "--package", "worker", \
     "celery", "-A", "worker.celery_app.celery_app", "worker", "--loglevel=INFO"]
