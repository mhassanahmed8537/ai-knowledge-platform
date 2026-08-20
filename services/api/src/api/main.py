from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from starlette.middleware.sessions import SessionMiddleware

from api.routers import (
    api_keys,
    auth,
    chat,
    documents,
    health,
    organizations,
    search,
    usage,
    users,
    webhooks,
)
from core.config import Settings, get_settings
from core.db import get_auth_engine, get_engine

# Secrets that ship as the local-dev default. Starting any non-local
# environment with one of these still set means every JWT/OAuth-state cookie
# is forgeable by anyone who has read this file, so it's treated as a
# configuration error rather than a warning.
_INSECURE_DEFAULTS = {
    "jwt_secret": "dev-insecure-change-me-0123456789abcdef",
    "session_secret": "dev-insecure-session-0123456789abcdef",
}


def _check_production_secrets(settings: Settings) -> None:
    if settings.is_local:
        return
    insecure = [
        field
        for field, default in _INSECURE_DEFAULTS.items()
        if getattr(settings, field) == default
    ]
    if insecure:
        raise RuntimeError(
            f"Refusing to start with insecure default secret(s) outside 'local': "
            f"{', '.join(insecure)}. Set unique values via environment variables."
        )


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    yield
    await get_engine().dispose()
    await get_auth_engine().dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    _check_production_secrets(settings)

    app = FastAPI(
        title="AI Knowledge Platform",
        version="0.1.0",
        lifespan=lifespan,
        # The interactive API map is a footprint an attacker shouldn't get
        # for free outside local dev; ops can still fetch openapi.json
        # directly through trusted tooling if needed.
        docs_url="/docs" if settings.is_local else None,
        redoc_url="/redoc" if settings.is_local else None,
        openapi_url="/openapi.json" if settings.is_local else None,
    )

    @app.middleware("http")
    async def _security_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        if not settings.is_local:
            # Only meaningful over TLS, which is terminated at the k8s
            # ingress (see infra/k8s) — harmless to send otherwise.
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return response

    # Carries the OAuth state/nonce across the provider redirect. Same-site
    # signed cookie; only used for the short-lived OAuth handshake.
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        same_site="lax",
        https_only=not settings.is_local,
    )
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(users.router)
    app.include_router(organizations.router)
    app.include_router(documents.router)
    app.include_router(api_keys.router)
    app.include_router(search.router)
    app.include_router(chat.router)
    app.include_router(usage.router)
    app.include_router(webhooks.router)
    return app


app = create_app()
