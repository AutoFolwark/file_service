# Tasks package for Celery
# Import modules so Celery autodiscover picks up task definitions and periodic schedules.
from app.tasks import file_status  # noqa: F401
