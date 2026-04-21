from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import health, projects
from app.api.errors import register_handlers
from app.config import get_settings
from app.utils.logger import configure_logging, get_logger


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    get_logger("app").info("app_start", env=settings.app_env)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Comic Drama Backend", version="0.1.0", lifespan=lifespan)
    register_handlers(app)
    app.include_router(health.router)
    app.include_router(projects.router, prefix="/api/v1")
    return app


app = create_app()
