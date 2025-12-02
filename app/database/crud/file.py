from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.crud.base import BaseService
from app.database.models.file import FileObject
from app.database.schemas.file import FileCreate, FileUpdate
from app.enums.file import FileVisibility, FileStatus, FileKind


class FileService(BaseService[FileObject, FileCreate, FileUpdate]):
    def __init__(self, session: AsyncSession):
        super().__init__(FileObject, session)

    async def mark_status(
        self, file_id: int, status: FileStatus, *, size_bytes: int | None = None
    ) -> FileObject | None:
        obj = await self.get(file_id)
        if not obj:
            return None
        obj.status = status
        if size_bytes is not None:
            obj.size_bytes = size_bytes
        await self.session.commit()
        await self.session.refresh(obj)
        return obj

    async def list_by_status(
        self, status: FileStatus, limit: int = 100
    ) -> Sequence[FileObject]:
        query = select(self.model).where(self.model.status == status).limit(limit)
        result = await self.session.execute(query)
        return result.scalars().all()
