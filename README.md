# AI Knowledge Platform

An enterprise-grade, multi-tenant **RAG (Retrieval-Augmented Generation)** platform. Organizations upload their private documents; their users ask natural-language questions and receive streamed, cited answers grounded in their own corpus — with strict tenant isolation, auth, observability, and cost tracking throughout.

> Status: **Phase 1 complete — auth & multi-tenancy.** JWT + OAuth auth, Postgres RLS tenant isolation, RBAC, API keys, and core CRUD are built and verified. Ingestion / retrieval / generation follow in later phases.

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

## First-time database setup

The runtime never connects as a superuser. Create the least-privilege roles once,
then run migrations (which apply the RLS policies and grant those roles):

```bash
docker compose up postgres redis minio -d

# 1. Create the app_user / app_auth roles (cluster-level, run once)
docker compose exec -T postgres psql -U postgres -d knowledge_platform < scripts/db_bootstrap.sql

# 2. Apply migrations (runs as the migration/owner role via MIGRATION_DATABASE_URL)
uv run alembic upgrade head
```

New migrations: `uv run alembic revision --autogenerate -m "message"` then review before `upgrade`.

## Auth & multi-tenancy

Three Postgres roles enforce least privilege:

| Role | Used by | RLS |
| --- | --- | --- |
| `postgres` | Alembic migrations only | owner (bypasses) |
| `app_auth` | Auth subsystem only (login/signup/refresh/oauth, API-key lookup) | **BYPASSRLS** — inherently cross-tenant |
| `app_user` | All authenticated business logic | **enforced** |

Every org-scoped table has `ENABLE`+`FORCE ROW LEVEL SECURITY` with a fail-closed
`org_isolation` policy keyed on the `app.current_org_id` GUC, which the API sets
per-request (via `set_config`) after decoding the caller's identity. `app_user`
therefore cannot read or write across tenants even if application code omits a
`WHERE org_id = …` clause.

- **Tokens:** short-lived JWT access token + rotating opaque refresh token (stored
  hashed, revoked on rotation/logout). Argon2 password hashing.
- **API keys:** `POST /api-keys` returns the plaintext once; only a SHA-256 is
  stored. Authenticate with `X-API-Key`; the key inherits its still-active
  creator's role.
- **RBAC:** `admin` / `member` / `read_only` via a `require_role()` dependency.

### OAuth setup (Google / GitHub)

Endpoints exist at `/auth/oauth/{provider}/authorize` and `/callback`. A provider
is enabled only when its credentials are set; otherwise `authorize` returns 404.
Configure in `.env`:

```
GOOGLE_CLIENT_ID=…       GOOGLE_CLIENT_SECRET=…
GITHUB_CLIENT_ID=…       GITHUB_CLIENT_SECRET=…
OAUTH_REDIRECT_BASE_URL=http://localhost:8000
```

Register the callback URL `…/auth/oauth/<provider>/callback` in the provider's
console. First OAuth login provisions a new org + admin (passwordless); a matching
email links to the existing user.

## Build plan

- ✅ **Phase 0** — Scaffolding, local dev stack, CI
- ✅ **Phase 1** — Auth (JWT + OAuth), multi-tenancy (RLS), RBAC, API keys, core CRUD, Alembic
- **Phase 2** — Ingestion (PDF end-to-end first): upload → chunk → embed → pgvector, via Celery
- **Phase 3** — Hybrid retrieval: BM25 (Postgres FTS) + vector, fusion/reranking
- **Phase 4** — Generation: LangGraph pipeline, SSE streaming, session memory, inline citations, prompt versioning
- **Phase 5** — Admin/ops: usage analytics, per-tenant cost tracking + budget alerts, webhooks
- **Phase 6** — K8s/Terraform/CI-CD hardening, security pass
