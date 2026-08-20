from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "local"

    # --- Database roles ---
    # Runtime, RLS-enforced least-privilege role used for all authenticated business logic.
    database_url: str = (
        "postgresql+asyncpg://app_user:app_password@localhost:5432/knowledge_platform"
    )
    # Trusted auth subsystem role (BYPASSRLS) used only for login/signup/refresh/oauth.
    auth_database_url: str = (
        "postgresql+asyncpg://app_auth:auth_password@localhost:5432/knowledge_platform"
    )
    # Superuser/owner role used exclusively by Alembic migrations.
    migration_database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/knowledge_platform"
    )

    redis_url: str = "redis://localhost:6379/0"

    # --- Object storage (MinIO locally, S3 in AWS) ---
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "documents"

    # --- Auth / JWT ---
    jwt_secret: str = "dev-insecure-change-me-0123456789abcdef"
    jwt_algorithm: str = "HS256"
    access_token_ttl_seconds: int = 15 * 60
    refresh_token_ttl_seconds: int = 14 * 24 * 60 * 60
    api_key_prefix: str = "akp_"
    # Signs the short-lived cookie that carries OAuth state across the redirect.
    session_secret: str = "dev-insecure-session-0123456789abcdef"

    # --- Rate limiting (Phase 6) ---
    # Redis-backed (not in-process): the API runs as multiple replicas in k8s,
    # so an in-process counter would let each pod enforce an independent
    # budget, silently multiplying the effective limit by replica count. This
    # is a defense-in-depth backstop — the ingress is the primary throttle
    # (see infra/k8s), so the default is deliberately generous rather than a
    # tight per-login-attempt limit.
    rate_limit_enabled: bool = True
    auth_rate_limit_per_minute: int = 20
    auth_rate_limit_window_seconds: int = 60

    # --- OAuth (Phase 1d; optional, empty disables the provider) ---
    google_client_id: str = ""
    google_client_secret: str = ""
    github_client_id: str = ""
    github_client_secret: str = ""
    oauth_redirect_base_url: str = "http://localhost:8000"

    # --- Ingestion (Phase 2) ---
    celery_broker_url: str = ""  # falls back to redis_url when empty
    chunk_size: int = 1000
    chunk_overlap: int = 150
    max_upload_bytes: int = 25 * 1024 * 1024
    # When true, POST /documents/upload enqueues ingestion automatically.
    auto_ingest_on_upload: bool = True

    # Embeddings: "fake" (deterministic, zero-cost dev default) or "openai".
    embedding_provider: str = "fake"
    embedding_dim: int = 1536
    openai_api_key: str = ""
    openai_embedding_model: str = "text-embedding-3-small"
    openai_base_url: str = "https://api.openai.com/v1"
    # Gemini. gemini-embedding-001 supports outputDimensionality, so it is asked
    # for `embedding_dim` vectors and fits the existing schema with no migration.
    gemini_api_key: str = ""
    gemini_embedding_model: str = "gemini-embedding-001"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"

    # --- Retrieval (Phase 3) ---
    retrieval_candidate_k: int = 50  # candidates fetched per arm before fusion
    rrf_k: int = 60  # Reciprocal Rank Fusion constant
    search_default_limit: int = 10
    search_max_limit: int = 50

    # --- Generation (Phase 4) ---
    # "stub" (zero-cost dev default), "anthropic", "openai", or "gemini".
    llm_provider: str = "stub"
    # Model names move fast — verify against ai.google.dev/gemini-api/docs/models.
    gemini_chat_model: str = "gemini-2.5-flash"
    anthropic_api_key: str = ""
    # Opus 4.8 is the current default Claude model. Note: temperature/top_p/top_k
    # are rejected by this model family, so the provider never sends them.
    anthropic_model: str = "claude-opus-4-8"
    openai_chat_model: str = "gpt-4o-mini"
    # Deliberately modest: grounded RAG answers are short. Raise for long-form.
    llm_max_tokens: int = 4096
    # Thinking depth / token spend: low | medium | high | xhigh | max.
    llm_effort: str = "medium"
    # Chunks passed to the model as numbered sources for citation.
    generation_context_chunks: int = 8
    # Prior turns replayed into the prompt (bounds context growth).
    max_history_messages: int = 20

    @property
    def broker_url(self) -> str:
        return self.celery_broker_url or self.redis_url

    @property
    def is_local(self) -> bool:
        return self.environment == "local"


@lru_cache
def get_settings() -> Settings:
    return Settings()
