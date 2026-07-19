from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.routers import health
from core.db import get_engine


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    yield
    await get_engine().dispose()


def create_app() -> FastAPI:
    app = FastAPI(title="AI Knowledge Platform", version="0.1.0", lifespan=lifespan)
    app.include_router(health.router)
    return app


app = create_app()
