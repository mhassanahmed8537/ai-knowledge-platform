# Alembic is deliberately not part of the api/worker runtime images (see
# api.Dockerfile) -- it's a `migrate` dependency-group (root pyproject.toml
# and libs/core/pyproject.toml), installed only here. Run as a k8s Job
# (infra/k8s/base/migration-job.yaml) before rolling out api/worker, using
# the superuser MIGRATION_DATABASE_URL -- never the app's own runtime role.
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.11.29 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

WORKDIR /repo

COPY pyproject.toml uv.lock alembic.ini ./
COPY libs/core ./libs/core
COPY services/api ./services/api
COPY services/worker ./services/worker
COPY migrations ./migrations
COPY scripts ./scripts

RUN uv sync --frozen --no-editable --package core --no-default-groups --group migrate

FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/repo/.venv/bin:$PATH"

RUN groupadd --gid 10001 appuser \
    && useradd --uid 10001 --gid appuser --no-create-home --shell /usr/sbin/nologin appuser

WORKDIR /repo
COPY --from=builder --chown=appuser:appuser /repo/.venv /repo/.venv
COPY --from=builder --chown=appuser:appuser /repo/alembic.ini /repo/alembic.ini
COPY --from=builder --chown=appuser:appuser /repo/migrations /repo/migrations
COPY --from=builder --chown=appuser:appuser /repo/scripts /repo/scripts

USER appuser

CMD ["python", "scripts/prepare_db.py"]
