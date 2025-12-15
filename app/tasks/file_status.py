import asyncio

from app.celery_app import celery_app
from app.core.logger import logger
from app.database.db.session import get_db_context
from app.services.file_status_sync import FileStatusSyncService


@celery_app.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(
        60.0, sync_pending_uploads.s(), name="sync_pending_uploads_every_minute"
    )
    logger.info("Scheduled periodic task sync_pending_uploads every 60s")


_event_loop: asyncio.AbstractEventLoop | None = None


def _get_event_loop() -> asyncio.AbstractEventLoop:
    global _event_loop
    if _event_loop is None or _event_loop.is_closed():
        _event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_event_loop)
    return _event_loop


async def _run_sync_pending_uploads(batch_size: int) -> list[int]:
    async with get_db_context() as session:
        service = FileStatusSyncService(session)
        logger.info("Starting pending upload sync", batch_size=batch_size)
        updated = await service.sync_pending_uploads(batch_size=batch_size)
        updated_ids = [item.id for item in updated]
        logger.info("Completed pending upload sync", updated=len(updated_ids), ids=updated_ids)
        return updated_ids


@celery_app.task(name="app.tasks.file_status.sync_pending_uploads")
def sync_pending_uploads(batch_size: int = 100) -> list[int]:
    loop = _get_event_loop()
    try:
        return loop.run_until_complete(_run_sync_pending_uploads(batch_size))
    except Exception:
        logger.exception("Failed to sync pending uploads", batch_size=batch_size)
        raise
