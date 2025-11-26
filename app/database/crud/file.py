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

    async def list_for_user(
        self,
        user_uuid: str,
        visibility: FileVisibility | None = None,
        folder: str | None = None,
        kind: FileKind | None = None,
    ) -> Sequence[FileObject]:
        stmt = select(FileObject).where(FileObject.user_uuid == user_uuid)
        if visibility:
            stmt = stmt.where(FileObject.visibility == visibility)
        if folder:
            stmt = stmt.where(FileObject.folder == folder)
        if kind:
            stmt = stmt.where(FileObject.kind == kind)
        result = await self.session.execute(stmt.order_by(FileObject.created_at.desc()))
        return result.scalars().all()

    async def mark_status(self, file_id: int, status: FileStatus) -> FileObject | None:
        obj = await self.get(file_id)
        if not obj:
            return None
        obj.status = status
        await self.session.commit()
        await self.session.refresh(obj)
        return obj
