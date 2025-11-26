from uuid import UUID

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db.session import get_async_db
from app.enums.file import FileKind, FileVisibility
from app.schemas.file import (
    BatchDownloadRequest,
    DownloadUrlResponse,
    FileListResponse,
    FileResponse,
    PresignUploadRequest,
    PresignUploadResponse,
)
from app.services.file_storage import FileStorageService

files_router = APIRouter(prefix="/files", tags=["files"])


@files_router.post("/presign-upload", response_model=PresignUploadResponse)
async def create_presigned_upload(
    data: PresignUploadRequest = Body(...),
    db: AsyncSession = Depends(get_async_db),
):
    service = FileStorageService(db)
    file_obj, upload_url, expires_in = await service.create_presigned_upload(data)
    return PresignUploadResponse(
        file_id=file_obj.id,
        bucket=file_obj.bucket,
        key=file_obj.key,
        upload_url=upload_url,
        expires_in=expires_in,
        headers={"Content-Type": file_obj.mime_type},
    )


@files_router.get("", response_model=FileListResponse)
async def list_files(
    user_uuid: UUID = Query(...),
    visibility: FileVisibility | None = Query(None),
    folder: str | None = Query(None),
    kind: FileKind | None = Query(None),
    db: AsyncSession = Depends(get_async_db),
):
    service = FileStorageService(db)
    files = await service.list_files(
        user_uuid=str(user_uuid), visibility=visibility, folder=folder, kind=kind
    )
    return FileListResponse(items=[FileResponse.model_validate(file) for file in files])


@files_router.get("/{file_id}/download-url", response_model=DownloadUrlResponse)
async def get_download_url(
    file_id: int,
    expires_in: int | None = Query(None, description="Override default expiry in seconds"),
    db: AsyncSession = Depends(get_async_db),
):
    service = FileStorageService(db)
    expires_value = expires_in or service.default_expiry
    url = await service.download_url(file_id=file_id, expires_in=expires_value)
    return DownloadUrlResponse(file_id=file_id, download_url=url, expires_in=expires_value)


@files_router.post("/download-urls", response_model=list[DownloadUrlResponse])
async def get_batch_download_urls(
    payload: BatchDownloadRequest = Body(...),
    db: AsyncSession = Depends(get_async_db),
):
    service = FileStorageService(db)
    urls: list[DownloadUrlResponse] = []
    expires_value = payload.expires_in or service.default_expiry
    for file_id in payload.file_ids:
        download_url = await service.download_url(file_id=file_id, expires_in=expires_value)
        urls.append(DownloadUrlResponse(file_id=file_id, download_url=download_url, expires_in=expires_value))
    return urls


@files_router.post("/{file_id}/mark-available", response_model=FileResponse)
async def mark_file_available(
    file_id: int,
    db: AsyncSession = Depends(get_async_db),
):
    service = FileStorageService(db)
    await service.mark_available(file_id)
    file_obj = await service.file_service.get(file_id)
    return FileResponse.model_validate(file_obj)
