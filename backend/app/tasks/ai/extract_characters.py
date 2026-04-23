from app.tasks.celery_app import celery_app


@celery_app.task(name="ai.extract_characters", queue="ai", bind=True)
def extract_characters(self, project_id: str, job_id: str) -> None:
    """Task 2 placeholder so the route can enqueue a real task safely."""
    return None
