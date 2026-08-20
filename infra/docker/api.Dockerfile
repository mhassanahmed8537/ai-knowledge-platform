# Multi-stage: the builder stage needs uv, a C toolchain-capable base, and the
# full source tree; none of that belongs in the image that actually runs in
# production. --no-editable makes the installed venv fully self-contained (a
# real site-packages install, not a symlink back to /repo), so the runtime
# stage below needs nothing but the venv itself -- not even uv.
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

RUN uv sync --frozen --no-dev --no-editable --package api

FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/repo/.venv/bin:$PATH"

# Least-privilege runtime identity; also lets k8s enforce runAsNonRoot with a
# known numeric UID (see infra/k8s/base/api-deployment.yaml).
RUN groupadd --gid 10001 appuser \
    && useradd --uid 10001 --gid appuser --no-create-home --shell /usr/sbin/nologin appuser

WORKDIR /repo
COPY --from=builder --chown=appuser:appuser /repo/.venv /repo/.venv

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz', timeout=2)" || exit 1

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
