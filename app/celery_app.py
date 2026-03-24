import os

from celery import Celery

from app.config import settings
from app.core.logger import logger


def _broker_url() -> str:
    return settings.RABBITMQ_URL

celery_app = Celery(
    "files",
    broker=_broker_url(),
    include=["app.tasks.file_status"],
)

celery_app.conf.timezone = os.getenv("TZ", "UTC")
celery_app.conf.result_backend = os.getenv("CELERY_RESULT_BACKEND")
# Discover tasks in app/tasks modules.
celery_app.autodiscover_tasks(["app"], related_name="tasks")
# Use in-memory beat scheduler so schedules come from code (no persistent DB file).
celery_app.conf.beat_scheduler = "celery.beat:Scheduler"

# Beat schedule will be configured in tasks modules.

logger.info(
    "Celery configured",
    broker_configured=bool(celery_app.conf.broker_url),
    result_backend_configured=bool(celery_app.conf.result_backend),
    timezone=celery_app.conf.timezone,
)

__all__ = ("celery_app",)
