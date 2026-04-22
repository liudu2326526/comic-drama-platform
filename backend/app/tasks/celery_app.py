from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "comic_drama",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.ai"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    task_default_queue="ai",
    task_always_eager=settings.celery_task_always_eager,
    task_routes={
        "ai.*": {"queue": "ai"},
        "video.*": {"queue": "video"},
    },
)


@celery_app.task(name="ai.ping")
def ping() -> str:
    return "pong"
