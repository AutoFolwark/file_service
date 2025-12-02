import sys
from pathlib import Path
from typing import Callable

import grpc
from fastapi import HTTPException, status
from pydantic import ValidationError

from app.core.logger import logger
from app.database.db.session import AsyncSessionLocal
from app.enums.file import FileKind, FileVisibility
from app.schemas.file import BatchPresignUploadRequest, PresignUploadRequest
from app.services.file_storage import FileStorageService

# Ensure generated protobuf modules are importable when running outside the package context.
GEN_PATH = Path(__file__).resolve().parent / "gen" / "python"
if str(GEN_PATH) not in sys.path:
    sys.path.insert(0, str(GEN_PATH))

from files.v1 import files_pb2, files_pb2_grpc  # noqa: E402


class FileServiceRpc(files_pb2_grpc.FileServiceServicer):
    def __init__(self, session_factory: Callable = AsyncSessionLocal):
        self._session_factory = session_factory

    async def CreatePresignedUpload(self, request, context):
        try:
            presign_request = self._build_presign_request(request)
        except (ValidationError, ValueError) as exc:
            logger.warning("Invalid CreatePresignedUpload payload", error=str(exc))
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("Invalid CreatePresignedUpload payload")
            return files_pb2.CreatePresignedUploadResponse()

        async with self._session_factory() as session:
            service = FileStorageService(session)
            try:
                file_obj, upload_url, expires_in = await service.create_presigned_upload(presign_request)
            except HTTPException as exc:
                self._set_context_from_http(exc, context, "create presigned upload")
                return files_pb2.CreatePresignedUploadResponse()
            except Exception as exc:  # pragma: no cover - defensive guard
                logger.exception("Unhandled error creating presigned upload", error=str(exc))
                context.set_code(grpc.StatusCode.INTERNAL)
                context.set_details("Internal error while creating presigned upload")
                return files_pb2.CreatePresignedUploadResponse()

        return self._build_presign_response(
            file_obj.id,
            file_obj.bucket,
            file_obj.key,
            upload_url,
            expires_in,
            file_obj.mime_type,
        )

    async def CreatePresignedUploadBatch(self, request, context):
        try:
            batch_request = self._build_batch_presign_request(request)
        except (ValidationError, ValueError) as exc:
            logger.warning("Invalid CreatePresignedUploadBatch payload", error=str(exc))
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("Invalid CreatePresignedUploadBatch payload")
            return files_pb2.CreatePresignedUploadBatchResponse()

        if batch_request.amount_of_files <= 0:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("amount_of_files must be greater than zero")
            return files_pb2.CreatePresignedUploadBatchResponse()

        async with self._session_factory() as session:
            service = FileStorageService(session)
            responses: list[files_pb2.CreatePresignedUploadResponse] = []
            try:
                for _ in range(batch_request.amount_of_files):
                    file_obj, upload_url, expires_in = await service.create_presigned_upload(batch_request)
                    responses.append(
                        self._build_presign_response(
                            file_obj.id,
                            file_obj.bucket,
                            file_obj.key,
                            upload_url,
                            expires_in,
                            file_obj.mime_type,
                        )
                    )
            except HTTPException as exc:
                self._set_context_from_http(exc, context, "create presigned upload batch")
                return files_pb2.CreatePresignedUploadBatchResponse()
            except Exception as exc:  # pragma: no cover - defensive guard
                logger.exception("Unhandled error creating presigned upload batch", error=str(exc))
                context.set_code(grpc.StatusCode.INTERNAL)
                context.set_details("Internal error while creating presigned upload batch")
                return files_pb2.CreatePresignedUploadBatchResponse()

        return files_pb2.CreatePresignedUploadBatchResponse(presigned_uploads=responses)

    async def GetDownloadUrl(self, request, context):
        expires_in = request.expires_in if request.HasField("expires_in") else None

        async with self._session_factory() as session:
            service = FileStorageService(session)
            target_expiry = expires_in or service.default_expiry
            try:
                download_url = await service.download_url(file_id=request.file_id, expires_in=target_expiry)
            except HTTPException as exc:
                self._set_context_from_http(exc, context, "get download url")
                return files_pb2.GetDownloadUrlResponse()
            except Exception as exc:  # pragma: no cover - defensive guard
                logger.exception("Unhandled error generating download url", error=str(exc), file_id=request.file_id)
                context.set_code(grpc.StatusCode.INTERNAL)
                context.set_details("Internal error while fetching download url")
                return files_pb2.GetDownloadUrlResponse()

        return files_pb2.GetDownloadUrlResponse(
            file_id=request.file_id,
            download_url=download_url,
            expires_in=target_expiry,
        )

    async def GetBatchDownloadUrls(self, request, context):
        expires_in = request.expires_in if request.HasField("expires_in") else None

        async with self._session_factory() as session:
            service = FileStorageService(session)
            target_expiry = expires_in or service.default_expiry
            urls: list[files_pb2.GetDownloadUrlResponse] = []
            try:
                for file_id in request.file_ids:
                    download_url = await service.download_url(file_id=file_id, expires_in=target_expiry)
                    urls.append(
                        files_pb2.GetDownloadUrlResponse(
                            file_id=file_id,
                            download_url=download_url,
                            expires_in=target_expiry,
                        )
                    )
            except HTTPException as exc:
                self._set_context_from_http(exc, context, "get batch download urls")
                return files_pb2.GetBatchDownloadUrlsResponse()
            except Exception as exc:  # pragma: no cover - defensive guard
                logger.exception("Unhandled error generating batch download urls", error=str(exc))
                context.set_code(grpc.StatusCode.INTERNAL)
                context.set_details("Internal error while fetching batch download urls")
                return files_pb2.GetBatchDownloadUrlsResponse()

        return files_pb2.GetBatchDownloadUrlsResponse(download_urls=urls)

    @staticmethod
    def _build_presign_response(
        file_id: int,
        bucket: str,
        key: str,
        upload_url: str,
        expires_in: int,
        mime_type: str,
    ) -> files_pb2.CreatePresignedUploadResponse:
        return files_pb2.CreatePresignedUploadResponse(
            file_id=file_id,
            bucket=bucket,
            key=key,
            upload_url=upload_url,
            expires_in=expires_in,
            http_method="PUT",
            headers={"Content-Type": mime_type},
        )

    def _build_presign_request(self, request) -> PresignUploadRequest:
        visibility = self._map_visibility(request.visibility)
        folder = request.folder if request.HasField("folder") else None
        kind = self._map_kind(request.kind, request.HasField("kind"))

        return PresignUploadRequest(
            file_name=request.file_name,
            mime_type=request.mime_type,
            visibility=visibility,
            folder=folder,
            kind=kind,
        )

    def _build_batch_presign_request(self, request) -> BatchPresignUploadRequest:
        visibility = self._map_visibility(request.visibility)
        folder = request.folder if request.HasField("folder") else None
        kind = self._map_kind(request.kind, request.HasField("kind"))

        return BatchPresignUploadRequest(
            file_name=request.file_name,
            mime_type=request.mime_type,
            visibility=visibility,
            folder=folder,
            kind=kind,
            amount_of_files=request.amount_of_files,
        )

    @staticmethod
    def _map_visibility(value: int) -> FileVisibility:
        if value == files_pb2.FILE_VISIBILITY_PUBLIC:
            return FileVisibility.PUBLIC
        return FileVisibility.PRIVATE

    @staticmethod
    def _map_kind(value: int, has_kind: bool) -> FileKind | None:
        if not has_kind or value == files_pb2.FILE_KIND_UNSPECIFIED:
            return None

        mapping = {
            files_pb2.FILE_KIND_IMAGE: FileKind.IMAGE,
            files_pb2.FILE_KIND_PDF: FileKind.PDF,
            files_pb2.FILE_KIND_DOCUMENT: FileKind.DOCUMENT,
            files_pb2.FILE_KIND_OTHER: FileKind.OTHER,
        }
        if value not in mapping:
            raise ValueError(f"Unsupported file kind value: {value}")
        return mapping[value]

    @staticmethod
    def _set_context_from_http(exc: HTTPException, context, action: str) -> None:
        status_map = {
            status.HTTP_400_BAD_REQUEST: grpc.StatusCode.INVALID_ARGUMENT,
            status.HTTP_401_UNAUTHORIZED: grpc.StatusCode.PERMISSION_DENIED,
            status.HTTP_403_FORBIDDEN: grpc.StatusCode.PERMISSION_DENIED,
            status.HTTP_404_NOT_FOUND: grpc.StatusCode.NOT_FOUND,
        }
        context.set_code(status_map.get(exc.status_code, grpc.StatusCode.INTERNAL))
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        context.set_details(detail or f"Failed to {action}")
