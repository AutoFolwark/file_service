from sqlalchemy.ext.asyncio import AsyncSession

from datetime import datetime, UTC, timedelta

from app.config import settings
from app.core.logger import logger
from app.database.crud.file import FileService
from app.database.models.file import FileObject
from app.enums.file import FileStatus
from app.services.file_storage import S3StorageClient
from app.services.rabbit_service.service import RabbitMQPublisher


class FileStatusSyncService:
    def __init__(self, db: AsyncSession, publisher: RabbitMQPublisher | None = None):
        self.db = db
        self.file_service = FileService(db)
        self.s3_client = S3StorageClient()
        self.publisher = publisher or RabbitMQPublisher()

    async def sync_pending_uploads(self, batch_size: int = 100) -> list[FileObject]:
        # Re-check pending uploads and previous failures (size unset) to recover late arrivals.
        pending_files = await self.file_service.list_by_statuses(
            [FileStatus.PENDING_UPLOAD, FileStatus.FAILED], limit=batch_size
        )
        logger.info(
            "Fetched pending uploads for sync",
            count=len(pending_files),
            batch_size=batch_size,
        )
        updated_files: list[FileObject] = []

        try:
            now = datetime.now(UTC)
            expiry_delta = timedelta(seconds=settings.S3_PRESIGNED_EXPIRES_IN)
            for file_obj in pending_files:
                exists, content_length = await self.s3_client.object_info(
                    bucket=file_obj.bucket, key=file_obj.key
                )
                if exists:
                    new_status = FileStatus.AVAILABLE
                    size_bytes = content_length if content_length is not None else None
                else:
                    expires_at = file_obj.created_at + expiry_delta
                    if now < expires_at:
                        logger.info(
                            "Upload still within presign window; skipping failure",
                            file_id=file_obj.id,
                            expires_at=expires_at.isoformat(),
                        )
                        continue
                    new_status = FileStatus.FAILED
                    size_bytes = None
                updated = await self.file_service.mark_status(
                    file_obj.id, new_status, size_bytes=size_bytes
                )
                if updated:
                    updated_files.append(updated)
                    logger.info(
                        "Updated file status",
                        file_id=updated.id,
                        status=new_status,
                        size=size_bytes,
                    )
                    if new_status == FileStatus.AVAILABLE:
                        await self._publish_file_uploaded(updated)
                else:
                    logger.warning(
                        "File status update returned no record",
                        file_id=file_obj.id,
                        status=new_status,
                    )
        finally:
            await self.publisher.close()

        logger.info("Sync complete", updated=len(updated_files))
        return updated_files

    async def _publish_file_uploaded(self, file_obj: FileObject) -> None:
        payload = {
            "id": file_obj.id,
            "bucket": file_obj.bucket,
            "key": file_obj.key,
            "file_name": file_obj.file_name,
            "mime_type": file_obj.mime_type,
            "size_bytes": file_obj.size_bytes,
            "visibility": file_obj.visibility.value,
            "kind": file_obj.kind.value,
            "folder": file_obj.folder,
            "status": file_obj.status.value,
        }
        try:
            await self.publisher.publish(routing_key="files.uploaded", payload=payload)
            logger.info(
                "Published file uploaded event",
                file_id=file_obj.id,
                routing_key="files.uploaded",
            )
        except Exception:
            logger.exception(
                "Failed to publish file uploaded event", file_id=file_obj.id
            )
