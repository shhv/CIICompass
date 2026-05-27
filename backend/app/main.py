from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.chat import router as chat_router
from .api.admin import router as admin_router
from .api.webex import router as webex_router
from .config import get_settings
from .scheduler import start_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = await start_scheduler()
    try:
        yield
    finally:
        if task is not None:
            task.cancel()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="CII Assistant", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(chat_router, prefix="/api")
    app.include_router(admin_router, prefix="/api")
    app.include_router(webex_router, prefix="/api")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
