from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import logger
from app.database.crud.file import FileService
from app.database.models.file import FileObject
from app.enums.file import FileStatus
from app.services.file_storage import S3StorageClient


class FileStatusSyncService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.file_service = FileService(db)
        self.s3_client = S3StorageClient()

    async def sync_pending_uploads(self, batch_size: int = 100) -> list[FileObject]:
        pending_files = await self.file_service.list_by_status(
            FileStatus.PENDING_UPLOAD, limit=batch_size
        )
        logger.info(
            "Fetched pending uploads for sync",
            count=len(pending_files),
            batch_size=batch_size,
        )
        updated_files: list[FileObject] = []

        for file_obj in pending_files:
            exists, content_length = await self.s3_client.object_info(
                bucket=file_obj.bucket, key=file_obj.key
            )
            new_status = FileStatus.AVAILABLE if exists else FileStatus.FAILED
            size_bytes = content_length if exists and content_length is not None else None
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
            else:
                logger.warning(
                    "File status update returned no record",
                    file_id=file_obj.id,
                    status=new_status,
                )

        logger.info("Sync complete", updated=len(updated_files))
        return updated_files
