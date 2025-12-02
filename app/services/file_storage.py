import re
from uuid import uuid4

import aioboto3
from botocore.config import Config
from botocore.exceptions import ClientError
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.logger import logger
from app.database.crud.file import FileService
from app.database.models.file import FileObject
from app.database.schemas.file import FileCreate
from app.enums.file import FileKind, FileVisibility
from app.schemas.file import PresignUploadRequest, BatchPresignUploadRequest


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
            "aws_access_key_id": settings.AWS_ACCESS_KEY_ID,
            "aws_secret_access_key": settings.AWS_SECRET_ACCESS_KEY,
            "use_ssl": settings.S3_USE_SSL,
            "config": self._config,
        }

    def _validated_client_kwargs(self) -> dict:
        kwargs = self._client_kwargs()
        if not kwargs["aws_access_key_id"] or not kwargs["aws_secret_access_key"]:
            logger.error("AWS credentials missing for S3 presign")
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
        expires_in: int,
    ) -> str:
        params = {
            "Bucket": bucket,
            "Key": key,
            "ContentType": mime_type,
        }

        async with aioboto3.Session().client("s3", **self._validated_client_kwargs()) as client:
            logger.debug(
                "Generating presigned upload URL",
                bucket=bucket,
                key=key,
                expires_in=expires_in,
                mime_type=mime_type,
            )
            return await client.generate_presigned_url(
                "put_object", Params=params, ExpiresIn=expires_in
            )

    async def presign_download(self, bucket: str, key: str, expires_in: int) -> str:
        params = {
            "Bucket": bucket,
            "Key": key,
        }
        async with aioboto3.Session().client("s3", **self._validated_client_kwargs()) as client:
            logger.debug(
                "Generating presigned download URL",
                bucket=bucket,
                key=key,
                expires_in=expires_in,
            )
            return await client.generate_presigned_url(
                "get_object", Params=params, ExpiresIn=expires_in
            )

    async def object_info(self, bucket: str, key: str) -> tuple[bool, int | None]:
        async with aioboto3.Session().client("s3", **self._validated_client_kwargs()) as client:
            try:
                response = await client.head_object(Bucket=bucket, Key=key)
                logger.debug("Retrieved S3 object info", bucket=bucket, key=key)
                return True, response.get("ContentLength")
            except ClientError as exc:
                error_code = exc.response.get("Error", {}).get("Code")
                if error_code in {"404", "NoSuchKey", "NotFound"}:
                    logger.warning("S3 object missing", bucket=bucket, key=key, error_code=error_code)
                    return False, None
                logger.exception("S3 head_object failed", bucket=bucket, key=key)
                raise


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

    def _build_key(self, folder: str, filename: str, visibility: FileVisibility) -> str:
        visibility_prefix = "public" if visibility == FileVisibility.PUBLIC else "private"
        safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", filename)
        unique_suffix = uuid4().hex
        return "/".join([visibility_prefix, folder, f"{unique_suffix}_{safe_name}"])

    async def create_presigned_upload(self, data: PresignUploadRequest) -> tuple:
        kind = data.kind or self._guess_kind(data.mime_type)
        folder = data.folder or self._default_folder(kind)

        key = self._build_key(folder, data.file_name, data.visibility)
        expires_in = settings.S3_PRESIGNED_EXPIRES_IN

        file_obj = await self.file_service.create(
            FileCreate(
                bucket=self.bucket,
                key=key,
                file_name=data.file_name,
                mime_type=data.mime_type,
                size_bytes=0,
                visibility=data.visibility,
                kind=kind,
                folder=folder,
            )
        )
        logger.info(
            "Created file metadata for upload",
            file_id=file_obj.id,
            bucket=file_obj.bucket,
            key=file_obj.key,
            visibility=data.visibility,
            kind=kind,
        )

        upload_url = await self.s3_client.presign_upload(
            bucket=self.bucket,
            key=key,
            mime_type=data.mime_type,
            expires_in=expires_in,
        )

        logger.info(
            "Presigned upload URL issued",
            file_id=file_obj.id,
            expires_in=expires_in,
            folder=folder,
        )
        return file_obj, upload_url, expires_in


    async def create_presigned_upload_batch(self, data: BatchPresignUploadRequest) -> list[tuple]:
        data_for_upload = []
        for i in range(1, data.amount_of_files):
            file_obj, upload_url, expires_in = await self.create_presigned_upload(data)
            data_for_upload.append((file_obj, upload_url, expires_in))
            logger.debug(
                "Added file to presign batch",
                file_id=file_obj.id,
                index=i,
                total=data.amount_of_files,
            )
        return data_for_upload


    async def _get_file(self, file_id: int) -> FileObject:
        file_obj = await self.file_service.get(file_id)
        if not file_obj:
            logger.warning("File not found", file_id=file_id)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        logger.debug("Fetched file metadata", file_id=file_obj.id, status=file_obj.status)
        return file_obj

    async def download_url(self, file_id: int, expires_in: int | None = None) -> str:
        file_obj = await self._get_file(file_id)

        url = await self.s3_client.presign_download(
            bucket=file_obj.bucket,
            key=file_obj.key,
            expires_in=expires_in or settings.S3_PRESIGNED_EXPIRES_IN,
        )
        logger.info(
            "Presigned download URL issued",
            file_id=file_id,
            expires_in=expires_in or settings.S3_PRESIGNED_EXPIRES_IN,
        )
        return url
