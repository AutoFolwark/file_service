from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.enums.file import FileKind, FileStatus, FileVisibility


class PresignUploadRequest(BaseModel):
    user_uuid: UUID
    file_name: str = Field(..., description="Original file name")
    mime_type: str = Field(..., description="MIME type of the file")
    size_bytes: int = Field(..., gt=0)
    visibility: FileVisibility = FileVisibility.PRIVATE
    folder: str | None = Field(None, description="Optional virtual folder prefix")
    kind: FileKind | None = Field(None, description="Override auto-detected kind for routing")


class PresignUploadResponse(BaseModel):
    file_id: int
    bucket: str
    key: str
    upload_url: str
    expires_in: int
    http_method: str = "PUT"
    headers: dict[str, Any] = {}


class FileResponse(BaseModel):
    id: int
    user_uuid: str
    bucket: str
    key: str
    file_name: str
    mime_type: str
    size_bytes: int
    visibility: FileVisibility
    kind: FileKind
    status: FileStatus
    folder: str | None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class DownloadUrlResponse(BaseModel):
    file_id: int
    download_url: str
    expires_in: int


class BatchDownloadRequest(BaseModel):
    file_ids: list[int]
    expires_in: int | None = Field(None, description="Override default expiry in seconds")


class FileListResponse(BaseModel):
    items: list[FileResponse]
