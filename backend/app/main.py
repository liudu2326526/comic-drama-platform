from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health, projects, jobs, storyboards, characters, scenes, shots, prompt_profiles
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
    settings = get_settings()
    app = FastAPI(title="Comic Drama Backend", version="0.1.0", lifespan=lifespan)
    
    # CORS
    origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    # 如果配置了环境变量则追加
    env_origins = getattr(settings, "backend_cors_origins", "")
    if env_origins:
        origins.extend([o.strip() for o in env_origins.split(",") if o.strip()])

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_handlers(app)
    app.include_router(health.router)
    app.include_router(projects.router, prefix="/api/v1")
    app.include_router(jobs.router, prefix="/api/v1")
    app.include_router(storyboards.router, prefix="/api/v1")
    app.include_router(characters.router, prefix="/api/v1")
    app.include_router(scenes.router, prefix="/api/v1")
    app.include_router(prompt_profiles.router, prefix="/api/v1")
    app.include_router(shots.router, prefix="/api/v1")
    return app


app = create_app()
