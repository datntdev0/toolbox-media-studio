"""Azure Blob Storage provider for public media assets."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from azure.storage.blob import BlobServiceClient, ContentSettings

from app.core.events.polling_queue_client import _storage_api_version

MAX_COVER_SIZE_BYTES = 1024 * 1024
_JPEG_SIGNATURE = b"\xff\xd8\xff"
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class BlobStorageError(RuntimeError):
    """Raised when a public blob cannot be written."""


class PublicBlobProvider:
    """Uploads media to the public blob container and returns its public URL."""

    def __init__(self, config: Any) -> None:
        self._service = BlobServiceClient.from_connection_string(
            config.connectionStrings.azStorageBlob,
            api_version=_storage_api_version(config)
        )
        self._container_name = getattr(config, "public_blob_container", "public")

    def upload_cover(self, novel_id: str, content: bytes, content_type: str) -> str:
        normalized_type = validate_cover_content(content, content_type)

        blob_name = f"novels/{novel_id}/cover-{uuid4().hex}"
        try:
            if self._service is None:
                raise BlobStorageError("Azure Blob Storage connection string is required")
            container = self._service.get_container_client(self._container_name)
            blob = container.get_blob_client(blob_name)
            blob.upload_blob(
                content,
                overwrite=True,
                content_settings=ContentSettings(content_type=normalized_type),
            )
            return blob.url
        except Exception as exc:
            raise BlobStorageError("Cover image could not be uploaded") from exc


def build_public_blob_provider(config: Any) -> PublicBlobProvider:
    return PublicBlobProvider(config)


def _has_valid_signature(content: bytes, content_type: str) -> bool:
    if content_type == "image/jpeg":
        return content.startswith(_JPEG_SIGNATURE)
    return content.startswith(_PNG_SIGNATURE)


def validate_cover_content(content: bytes, content_type: str) -> str:
    normalized_type = content_type.lower().split(";", 1)[0].strip()
    if len(content) > MAX_COVER_SIZE_BYTES:
        raise BlobStorageError("Cover image must not exceed 1 MB")
    if normalized_type not in {"image/jpeg", "image/png"}:
        raise BlobStorageError("Cover image must be a JPEG or PNG")
    if not content or not _has_valid_signature(content, normalized_type):
        raise BlobStorageError("Cover image content is invalid")
    return normalized_type
