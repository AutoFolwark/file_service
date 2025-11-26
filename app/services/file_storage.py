import re
from uuid import uuid4

import aioboto3
from botocore.config import Config
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.crud.file import FileService
from app.database.schemas.file import FileCreate
from app.enums.file import FileKind, FileStatus, FileVisibility
from app.schemas.file import PresignUploadRequest


class S3StorageClient:
    def __init__(self):
        s3_config = {
            "signature_version": "s3v4",
            "s3": {"addressing_style": "path" if settings.S3_FORCE_PATH_STYLE else "auto"},
        }
        self._config = Config(**s3_config)

    def _client_kwargs(self) -> dict:
        return {
            "region_name": settings.AWS_REGION,
            "endpoint_url": settings.S3_ENDPOINT_URL,
            "aws_access_key_id": settings.AWS_ACCESS_KEY_ID,
            "aws_secret_access_key": settings.AWS_SECRET_ACCESS_KEY,
            "use_ssl": settings.S3_USE_SSL,
            "config": self._config,
        }

    def _validated_client_kwargs(self) -> dict:
        kwargs = self._client_kwargs()
        if not kwargs["aws_access_key_id"] or not kwargs["aws_secret_access_key"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="AWS credentials are not configured (AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY).",
            )
        return kwargs

    async def presign_upload(
        self,
        bucket: str,
        key: str,
        mime_type: str,
        visibility: FileVisibility,
        expires_in: int,
    ) -> str:
        params = {
            "Bucket": bucket,
            "Key": key,
            "ContentType": mime_type,
        }
        if visibility == FileVisibility.PUBLIC:
            params["ACL"] = "public-read"

        async with aioboto3.Session().client("s3", **self._validated_client_kwargs()) as client:
            return await client.generate_presigned_url(
                "put_object", Params=params, ExpiresIn=expires_in
            )

    async def presign_download(self, bucket: str, key: str, expires_in: int) -> str:
        params = {
            "Bucket": bucket,
            "Key": key,
        }
        async with aioboto3.Session().client("s3", **self._validated_client_kwargs()) as client:
            return await client.generate_presigned_url(
                "get_object", Params=params, ExpiresIn=expires_in
            )


class FileStorageService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.bucket = settings.S3_BUCKET
        self.file_service = FileService(db)
        self.s3_client = S3StorageClient()
        self.default_expiry = settings.S3_PRESIGNED_EXPIRES_IN

    @staticmethod
    def _guess_kind(mime_type: str) -> FileKind:
        if mime_type.startswith("image/"):
            return FileKind.IMAGE
        if mime_type in {"application/pdf"}:
            return FileKind.PDF
        if mime_type.startswith("application/"):
            return FileKind.DOCUMENT
        return FileKind.OTHER

    @staticmethod
    def _default_folder(kind: FileKind) -> str:
        if kind == FileKind.IMAGE:
            return "images"
        if kind == FileKind.PDF:
            return "pdfs"
        if kind == FileKind.DOCUMENT:
            return "documents"
        return "files"

    def _build_key(self, user_uuid: str, folder: str, filename: str) -> str:
        safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", filename)
        unique_suffix = uuid4().hex
        return "/".join([folder, user_uuid, f"{unique_suffix}_{safe_name}"])

    async def create_presigned_upload(self, data: PresignUploadRequest) -> tuple:
        kind = data.kind or self._guess_kind(data.mime_type)
        folder = data.folder or self._default_folder(kind)

        key = self._build_key(str(data.user_uuid), folder, data.file_name)
        expires_in = settings.S3_PRESIGNED_EXPIRES_IN

        file_obj = await self.file_service.create(
            FileCreate(
                user_uuid=str(data.user_uuid),
                bucket=self.bucket,
                key=key,
                file_name=data.file_name,
                mime_type=data.mime_type,
                size_bytes=data.size_bytes,
                visibility=data.visibility,
                kind=kind,
                folder=folder,
            )
        )

        upload_url = await self.s3_client.presign_upload(
            bucket=self.bucket,
            key=key,
            mime_type=data.mime_type,
            visibility=data.visibility,
            expires_in=expires_in,
        )

        return file_obj, upload_url, expires_in

    async def download_url(self, file_id: int, expires_in: int | None = None) -> str:
        file_obj = await self.file_service.get(file_id)
        if not file_obj:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

        if file_obj.visibility == FileVisibility.PUBLIC and settings.S3_PUBLIC_BASE_URL:
            return f"{settings.S3_PUBLIC_BASE_URL.rstrip('/')}/{file_obj.key}"

        return await self.s3_client.presign_download(
            bucket=file_obj.bucket,
            key=file_obj.key,
            expires_in=expires_in or settings.S3_PRESIGNED_EXPIRES_IN,
        )

    async def mark_available(self, file_id: int) -> FileStatus:
        updated = await self.file_service.mark_status(file_id, FileStatus.AVAILABLE)
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        return updated.status

    async def list_files(
        self,
        user_uuid: str,
        visibility: FileVisibility | None = None,
        folder: str | None = None,
        kind: FileKind | None = None,
    ):
        return await self.file_service.list_for_user(
            user_uuid=str(user_uuid), visibility=visibility, folder=folder, kind=kind
        )
