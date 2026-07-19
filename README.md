# AI Knowledge Platform

An enterprise-grade, multi-tenant **RAG (Retrieval-Augmented Generation)** platform. Organizations upload their private documents; their users ask natural-language questions and receive streamed, cited answers grounded in their own corpus — with strict tenant isolation, auth, observability, and cost tracking throughout.

> Status: **Phase 0 — scaffolding & local dev.** The application logic (auth, ingestion, retrieval, generation) is built out in subsequent phases.

## Architecture at a glance

| Concern | Choice |
| --- | --- |
| Backend API | Python 3.12, FastAPI (async) |
| Background workers | Celery (Redis broker) |
| Database | PostgreSQL 16 + `pgvector` |
| Tenant isolation | Single DB, **Postgres Row-Level Security** keyed on `tenant_id` |
| Cache / queue | Redis |
| Object storage | S3 in AWS; **MinIO** locally |
| LLMs | OpenAI + Anthropic behind a provider-agnostic abstraction |
| Orchestration | LangGraph (retrieve → generate → cite) |
| Infra | Docker, Kubernetes, Terraform, AWS (IaC written to be production-correct; validated via `plan`/kind, not continuously deployed) |
| CI/CD | GitHub Actions |

## Repository layout

```
.
├── services/
│   ├── api/            # FastAPI app        (package: api,    src/ layout)
│   └── worker/         # Celery workers     (package: worker, src/ layout)
├── libs/
│   └── core/           # shared lib (config, db, schemas, providers, rag) — imported by both services
├── migrations/         # Alembic (added in Phase 1)
├── infra/
│   ├── docker/         # service Dockerfiles
│   ├── terraform/      # modules/ + envs/{dev,...}
│   └── k8s/            # base/ + overlays/{dev,...}
├── tests/
├── docs/
├── .github/workflows/  # CI
├── docker-compose.yml  # local Postgres+pgvector, Redis, MinIO, api, worker
└── pyproject.toml      # uv workspace root (Python 3.12)
```

This is a **[uv](https://docs.astral.sh/uv/) workspace**: `libs/core`, `services/api`, and `services/worker` are workspace members. Both services depend on `core` via `{ workspace = true }`. Each service uses a `src/<package>` layout so the two `app`-style packages never collide in the shared virtualenv.

## Prerequisites

- Python 3.12 (the workspace pins `>=3.12,<3.13`)
- [`uv`](https://docs.astral.sh/uv/) (`pip install uv`)
- Docker + Docker Compose (for the local stack)

## Local development

```bash
# 1. Install all workspace packages + dev tools into .venv
uv sync --all-packages

# 2. Copy env template
cp .env.example .env

# 3. Bring up Postgres (pgvector), Redis, MinIO, api, worker
docker compose up --build

# --- or run the app directly against compose-managed infra ---
docker compose up postgres redis minio -d
uv run --package api uvicorn api.main:app --reload
uv run --package worker celery -A worker.celery_app.celery_app worker --loglevel=INFO
```

- API: http://localhost:8000  · Swagger UI: http://localhost:8000/docs  · Health: http://localhost:8000/healthz
- MinIO console: http://localhost:9001 (`minioadmin` / `minioadmin`)

## Quality gates

```bash
uv run ruff check .        # lint
uv run ruff format .       # format
uv run mypy libs/core/core services/api/src/api services/worker/src/worker
uv run pytest -q           # tests
pre-commit install         # enable git hooks
```

CI (`.github/workflows/ci.yml`) runs lint + format-check + mypy, and a separate test job with Postgres/Redis service containers, on every push to `main` and every PR.

## Build plan

- **Phase 0** — Scaffolding, local dev stack, CI *(current)*
- **Phase 1** — Auth (JWT + OAuth), multi-tenancy (RLS), RBAC, API keys, core CRUD, Alembic
- **Phase 2** — Ingestion (PDF end-to-end first): upload → chunk → embed → pgvector, via Celery
- **Phase 3** — Hybrid retrieval: BM25 (Postgres FTS) + vector, fusion/reranking
- **Phase 4** — Generation: LangGraph pipeline, SSE streaming, session memory, inline citations, prompt versioning
- **Phase 5** — Admin/ops: usage analytics, per-tenant cost tracking + budget alerts, webhooks
- **Phase 6** — K8s/Terraform/CI-CD hardening, security pass
