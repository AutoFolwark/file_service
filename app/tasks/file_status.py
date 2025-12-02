import asyncio

from celery.schedules import crontab

from app.celery_app import celery_app
from app.core.logger import logger
from app.database.db.session import AsyncSessionLocal
from app.services.file_status_sync import FileStatusSyncService


@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    # Every minute by default; adjust as needed via CELERY_BEAT_SCHEDULE override.
    sender.add_periodic_task(
        60.0, sync_pending_uploads.s(), name="sync_pending_uploads_every_minute"
    )
    logger.debug("Scheduled periodic task sync_pending_uploads every 60s")


@celery_app.task(name="app.tasks.file_status.sync_pending_uploads")
def sync_pending_uploads(batch_size: int = 100) -> list[int]:
    async def _run() -> list[int]:
        async with AsyncSessionLocal() as session:
            service = FileStatusSyncService(session)
            logger.info("Starting pending upload sync", batch_size=batch_size)
            updated = await service.sync_pending_uploads(batch_size=batch_size)
            updated_ids = [item.id for item in updated]
            logger.info("Completed pending upload sync", updated=len(updated_ids), ids=updated_ids)
            return updated_ids

    try:
        return asyncio.run(_run())
    except Exception:
        logger.exception("Failed to sync pending uploads", batch_size=batch_size)
        raise
