from enum import Enum


class FileVisibility(str, Enum):
    PUBLIC = "public"
    PRIVATE = "private"


class FileStatus(str, Enum):
    PENDING_UPLOAD = "pending_upload"
    AVAILABLE = "available"
    FAILED = "failed"


class FileKind(str, Enum):
    IMAGE = "image"
    PDF = "pdf"
    DOCUMENT = "document"
    OTHER = "other"
