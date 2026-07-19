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

    # --- OAuth (Phase 1d; optional, empty disables the provider) ---
    google_client_id: str = ""
    google_client_secret: str = ""
    github_client_id: str = ""
    github_client_secret: str = ""
    oauth_redirect_base_url: str = "http://localhost:8000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
