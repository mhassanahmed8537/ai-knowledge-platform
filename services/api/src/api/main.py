from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from api.routers import api_keys, auth, documents, health, users
from core.config import get_settings
from core.db import get_auth_engine, get_engine


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    yield
    await get_engine().dispose()
    await get_auth_engine().dispose()


def create_app() -> FastAPI:
    app = FastAPI(title="AI Knowledge Platform", version="0.1.0", lifespan=lifespan)
    # Carries the OAuth state/nonce across the provider redirect. Same-site
    # signed cookie; only used for the short-lived OAuth handshake.
    app.add_middleware(
        SessionMiddleware,
        secret_key=get_settings().session_secret,
        same_site="lax",
        https_only=False,
    )
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(users.router)
    app.include_router(documents.router)
    app.include_router(api_keys.router)
    return app


app = create_app()
