"""Public blob provider tests for chapter audio artifacts."""

from types import SimpleNamespace
from typing import Any

from app.providers.blob_storage_provider import PublicBlobProvider


class FakeBlob:
    def __init__(self, name: str) -> None:
        self.url = f"https://storage.test/public/{name}"
        self.uploads: list[tuple[bytes, dict[str, Any]]] = []

    def upload_blob(self, content: bytes, **kwargs: Any) -> None:
        self.uploads.append((content, kwargs))


class FakeContainer:
    def __init__(self) -> None:
        self.blobs: dict[str, FakeBlob] = {}
        self.listed_names: list[str] = []
        self.deleted: list[str] = []

    def get_blob_client(self, name: str) -> FakeBlob:
        return self.blobs.setdefault(name, FakeBlob(name))

    def list_blobs(self, *, name_starts_with: str) -> list[SimpleNamespace]:
        return [
            SimpleNamespace(name=name)
            for name in self.listed_names
            if name.startswith(name_starts_with)
        ]

    def delete_blob(self, name: str) -> None:
        self.deleted.append(name)


class FakeBlobService:
    def __init__(self, container: FakeContainer) -> None:
        self.container = container

    def get_container_client(self, name: str) -> FakeContainer:
        assert name == "public"
        return self.container


def _provider(container: FakeContainer) -> PublicBlobProvider:
    provider = object.__new__(PublicBlobProvider)
    provider._service = FakeBlobService(container)
    provider._container_name = "public"
    return provider


def test_uploads_deterministic_chapter_artifacts_with_content_types() -> None:
    container = FakeContainer()
    provider = _provider(container)

    audio_url = provider.upload_task_audio("workspace-1", "chapter-1", b"wav")
    subtitle_url = provider.upload_task_subtitle("workspace-1", "chapter-1", b"srt")

    assert audio_url.endswith("/workspaces/workspace-1/chapter-1/audio.wav")
    assert subtitle_url.endswith("/workspaces/workspace-1/chapter-1/captions.srt")
    audio_upload = container.blobs[
        "workspaces/workspace-1/chapter-1/audio.wav"
    ].uploads[0]
    subtitle_upload = container.blobs[
        "workspaces/workspace-1/chapter-1/captions.srt"
    ].uploads[0]
    assert audio_upload[0] == b"wav"
    assert audio_upload[1]["overwrite"] is True
    assert audio_upload[1]["content_settings"].content_type == "audio/wav"
    assert subtitle_upload[0] == b"srt"
    assert subtitle_upload[1]["content_settings"].content_type == (
        "application/x-subrip; charset=utf-8"
    )


def test_cleanup_deletes_only_allowlisted_legacy_task_audio() -> None:
    container = FakeContainer()
    prefix = "workspaces/workspace-1/chapter-1/"
    container.listed_names = [
        f"{prefix}0.wav",
        f"{prefix}12.wav",
        f"{prefix}export.wav",
        f"{prefix}audio.wav",
        f"{prefix}captions.srt",
        f"{prefix}notes.wav",
        "workspaces/workspace-1/chapter-2/0.wav",
    ]

    _provider(container).delete_legacy_task_audio("workspace-1", "chapter-1")

    assert container.deleted == [
        f"{prefix}0.wav",
        f"{prefix}12.wav",
        f"{prefix}export.wav",
    ]
