from datetime import datetime, UTC
from sqlalchemy import BigInteger, DateTime, Enum as SAEnum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.models import Base
from app.enums.file import FileKind, FileStatus, FileVisibility


class FileObject(Base):
    __tablename__ = "file_object"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_uuid: Mapped[str] = mapped_column(String(length=36), nullable=False)
    bucket: Mapped[str] = mapped_column(String(length=255), nullable=False)
    key: Mapped[str] = mapped_column(String(length=512), nullable=False, unique=True)
    file_name: Mapped[str] = mapped_column(String(length=255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(length=128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    visibility: Mapped[FileVisibility] = mapped_column(
        SAEnum(FileVisibility, name="file_visibility"), nullable=False
    )
    kind: Mapped[FileKind] = mapped_column(SAEnum(FileKind, name="file_kind"), nullable=False)
    status: Mapped[FileStatus] = mapped_column(
        SAEnum(FileStatus, name="file_status"),
        nullable=False,
        default=FileStatus.PENDING_UPLOAD,
    )
    folder: Mapped[str | None] = mapped_column(String(length=128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.now(UTC), onupdate=datetime.now(UTC)
    )
