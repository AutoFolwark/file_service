from pydantic import BaseModel, ConfigDict

from app.enums.file import FileKind, FileStatus, FileVisibility


class FileCreate(BaseModel):
    bucket: str
    key: str
    file_name: str
    mime_type: str
    size_bytes: int
    visibility: FileVisibility
    kind: FileKind
    folder: str | None = None
    status: FileStatus = FileStatus.PENDING_UPLOAD


class FileUpdate(BaseModel):
    file_name: str | None = None
    mime_type: str | None = None
    visibility: FileVisibility | None = None
    status: FileStatus | None = None
    folder: str | None = None


class FileRead(FileCreate):
    id: int

    model_config = ConfigDict(from_attributes=True)
