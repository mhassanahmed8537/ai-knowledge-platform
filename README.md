# AI Knowledge Platform

An enterprise-grade, multi-tenant **RAG (Retrieval-Augmented Generation)** platform. Organizations upload their private documents; their users ask natural-language questions and receive streamed, cited answers grounded in their own corpus — with strict tenant isolation, auth, observability, and cost tracking throughout.

> Status: **Phase 3 complete — hybrid retrieval.** On top of Phase 1 (auth,
> RLS, RBAC) and Phase 2 (PDF → MinIO → Celery → pgvector), `POST /search` now
> does hybrid retrieval: Postgres full-text (BM25-style) + pgvector similarity,
> fused with Reciprocal Rank Fusion. LLM generation follows in Phase 4.

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
uv run pytest -q           # unit + integration tests
pre-commit install         # enable git hooks
```

Unit tests (`tests/unit`) need no services. Integration tests (`tests/integration`)
drive the real app via httpx against Postgres and are **auto-skipped when the DB is
unreachable** — bring up the stack and run `prepare_db.py` first to exercise them.
They cover the auth flow, tenant RLS isolation, the RBAC matrix, and the API-key
lifecycle, each in its own throwaway `itest-` org (cleaned up on teardown).

CI (`.github/workflows/ci.yml`) runs lint + format-check + mypy, and a separate test
job that spins up Postgres/Redis service containers, runs `prepare_db.py`, then the
full suite — on every push to `main` and every PR.

## First-time database setup

The runtime never connects as a superuser. Create the least-privilege roles once,
then run migrations (which apply the RLS policies and grant those roles):

```bash
cp .env.example .env
docker compose up postgres redis minio -d

# Create the app_user / app_auth roles AND apply migrations in one step:
uv run python scripts/prepare_db.py
```

> Keep `.env` in sync with `.env.example` after pulling — a stale `DATABASE_URL`
> pointing at a superuser silently disables RLS. `GET /healthz` guards against
> this: it reports `"rls": "enforced"` and flips to `"UNSAFE-bypass"` /
> `"status": "degraded"` if the runtime role can bypass RLS.

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

## Ingestion (Phase 2)

`POST /documents/upload` (multipart PDF) stores the file in MinIO/S3, creates a
`pending` document, and — after the request commits — enqueues a Celery job. The
worker runs the pipeline as the RLS-enforced `app_user` with the tenant's org
context bound:

```
upload → MinIO → Celery → pypdf extract → chunk → embed → pgvector → status: ready
```

- **Chunking:** dependency-free word-boundary sliding window (`chunk_size` /
  `chunk_overlap` configurable).
- **Embeddings:** pluggable provider. Default `fake` — deterministic, unit-norm,
  **zero-cost**, reproducible in tests. Set `EMBEDDING_PROVIDER=openai` +
  `OPENAI_API_KEY` to use `text-embedding-3-small` (same 1536 dims → no schema
  change). Vectors land in a `document_chunks` table with an HNSW cosine index,
  itself RLS-scoped by `org_id`.
- **Status:** poll `GET /documents/{id}` (`pending`→`processing`→`ready`/`failed`,
  with `error` on failure). Inspect results via `GET /documents/{id}/chunks`.

The pipeline lives in `libs/core` as a plain async function, so integration tests
drive it directly; the Celery worker path is verified end-to-end against the stack.

## Hybrid retrieval (Phase 3)

`POST /search` `{query, mode, limit}` returns ranked chunks scoped to the caller's
tenant (RLS). Two retrieval arms run on the same RLS-bound session:

- **Lexical (BM25-style):** a generated `tsvector` column + GIN index; ranked with
  `ts_rank_cd` over `plainto_tsquery`.
- **Vector:** pgvector cosine distance over the chunk embeddings (HNSW index). The
  query is embedded with the *same* provider used at ingestion.

They are combined with **Reciprocal Rank Fusion** (`score = Σ 1/(k + rank)`), which
is score-scale agnostic — no need to normalise the two very different score ranges
against each other. `mode` selects `hybrid` (default), `vector`, or `lexical`.

> With the default `fake` embedder (feature-hashing), the vector arm rewards shared
> vocabulary — enough to exercise fusion realistically offline. True semantic
> matching arrives by setting `EMBEDDING_PROVIDER=openai`.

## Build plan

- ✅ **Phase 0** — Scaffolding, local dev stack, CI
- ✅ **Phase 1** — Auth (JWT + OAuth), multi-tenancy (RLS), RBAC, API keys, core CRUD, Alembic
- ✅ **Phase 2** — Ingestion: PDF upload → MinIO → Celery → extract → chunk → embed → pgvector
- ✅ **Phase 3** — Hybrid retrieval: BM25 (Postgres FTS) + pgvector, Reciprocal Rank Fusion
- **Phase 4** — Generation: LangGraph pipeline, SSE streaming, session memory, inline citations, prompt versioning
- **Phase 5** — Admin/ops: usage analytics, per-tenant cost tracking + budget alerts, webhooks
- **Phase 6** — K8s/Terraform/CI-CD hardening, security pass
