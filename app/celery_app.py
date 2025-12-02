import os

from celery import Celery

from app.config import settings
from app.core.logger import logger


def _broker_url() -> str:
    return settings.REDIS_URL

def _result_backend() -> str:
    return settings.REDIS_URL

celery_app = Celery(
    "vinaslt_files",
    broker=_broker_url(),
    backend=_result_backend(),
)

celery_app.conf.timezone = os.getenv("TZ", "UTC")
celery_app.autodiscover_tasks(["app.tasks"])

# Beat schedule will be configured in tasks modules.

logger.info(
    "Celery configured",
    broker=bool(settings.REDIS_URL),
    timezone=celery_app.conf.timezone,
)

__all__ = ("celery_app",)
