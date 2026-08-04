"""Microsoft Foundry Speech batch synthesis provider tests."""

from __future__ import annotations

import io
import json
import zipfile
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any, cast

import httpx
import pytest

from app.core.config.app_config import AppConfig
from app.providers import speech_service_provider as speech_module
from app.providers.speech_service_provider import (
    MicrosoftFoundrySpeechProvider,
    SpeechServiceError,
    SpeechSynthesisArtifact,
)

_WAV_DATA = b"RIFF\x04\x00\x00\x00WAVEdata"


def _config(
    *,
    endpoint: str = "https://speech.example.test/",
    api_key: str = "test-key",
    batch_timeout_seconds: int = 1800,
    poll_interval_seconds: int = 1,
) -> AppConfig:
    return cast(
        AppConfig,
        SimpleNamespace(
            azure_speech=SimpleNamespace(
                endpoint=endpoint,
                api_key=api_key,
                batch_timeout_seconds=batch_timeout_seconds,
                poll_interval_seconds=poll_interval_seconds,
            )
        ),
    )


def _boundary(text: str, offset: int, duration: int) -> dict[str, Any]:
    return {"Text": text, "AudioOffset": offset, "Duration": duration}


def _result_zip(
    *,
    sentence_boundaries: object,
    word_boundaries: object,
    audio_data: bytes = _WAV_DATA,
    extra_files: dict[str, bytes] | None = None,
) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("0001.wav", audio_data)
        archive.writestr("0001.sentence.json", json.dumps(sentence_boundaries))
        archive.writestr("0001.word.json", json.dumps(word_boundaries))
        for name, data in (extra_files or {}).items():
            archive.writestr(name, data)
    return output.getvalue()


def _provider(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    config: AppConfig | None = None,
) -> MicrosoftFoundrySpeechProvider:
    transport = httpx.MockTransport(handler)
    return MicrosoftFoundrySpeechProvider(
        config or _config(),
        client_factory=lambda: httpx.Client(transport=transport),
    )


def _success_handler(
    result_zip: bytes,
    calls: list[httpx.Request],
) -> Callable[[httpx.Request], httpx.Response]:
    poll_statuses = [
        {"status": "Running"},
        {
            "status": "Succeeded",
            "outputs": {"result": "https://results.example.test/results.zip"},
        },
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.method == "PUT":
            return httpx.Response(201, json={"status": "NotStarted"})
        if request.method == "DELETE":
            return httpx.Response(204)
        if request.url.host == "results.example.test":
            return httpx.Response(200, content=result_zip)
        return httpx.Response(200, json=poll_statuses.pop(0))

    return handler


def test_synthesize_submits_batch_and_returns_wav_and_exact_srt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[httpx.Request] = []
    sentences = ["  Xin   chào thế giới. ", "Second\nline."]
    archive = _result_zip(
        sentence_boundaries=[
            _boundary("Xin chào thế giới.", 50, 1_450),
            _boundary("Second line.", 1_600, 2_000),
        ],
        word_boundaries=[_boundary("unused", 0, 1)],
    )
    monkeypatch.setattr(speech_module.time, "sleep", lambda _seconds: None)

    artifact = _provider(_success_handler(archive, calls)).synthesize(
        sentences,
        " vi-VN-HoaiMyNeural ",
    )

    assert artifact == SpeechSynthesisArtifact(
        audio_data=_WAV_DATA,
        subtitle_data=(
            "1\r\n00:00:00,050 --> 00:00:01,500\r\nXin chào thế giới.\r\n\r\n"
            "2\r\n00:00:01,600 --> 00:00:03,600\r\nSecond line.\r\n"
        ).encode(),
    )
    put_request = next(request for request in calls if request.method == "PUT")
    assert put_request.url.path.startswith("/texttospeech/batchsyntheses/speech-")
    assert dict(put_request.url.params) == {"api-version": "2024-04-01"}
    assert put_request.headers["Ocp-Apim-Subscription-Key"] == "test-key"
    assert json.loads(put_request.content) == {
        "inputKind": "PlainText",
        "inputs": [{"content": "Xin chào thế giới.\r\nSecond line."}],
        "synthesisConfig": {"voice": "vi-VN-HoaiMyNeural"},
        "properties": {
            "outputFormat": "riff-24khz-16bit-mono-pcm",
            "wordBoundaryEnabled": True,
            "sentenceBoundaryEnabled": True,
            "concatenateResult": True,
            "decompressOutputFiles": False,
        },
    }
    assert [request.method for request in calls] == ["PUT", "GET", "GET", "GET", "DELETE"]


def test_synthesize_falls_back_to_sequential_word_boundaries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[httpx.Request] = []
    archive = _result_zip(
        sentence_boundaries=[_boundary("Hello, world! Next.", 0, 1_500)],
        word_boundaries=[
            _boundary("Hello", 0, 300),
            _boundary(",", 300, 50),
            _boundary("world", 400, 400),
            _boundary("!", 800, 100),
            _boundary("Next", 1_000, 400),
            _boundary(".", 1_400, 100),
        ],
    )
    monkeypatch.setattr(speech_module.time, "sleep", lambda _seconds: None)

    artifact = _provider(_success_handler(archive, calls)).synthesize(
        ["Hello, world!", "Next."],
        "en-US-JennyNeural",
    )

    assert artifact.subtitle_data.decode() == (
        "1\r\n00:00:00,000 --> 00:00:00,900\r\nHello, world!\r\n\r\n"
        "2\r\n00:00:01,000 --> 00:00:01,500\r\nNext.\r\n"
    )


@pytest.mark.parametrize(
    ("config", "sentences", "voice", "message"),
    [
        (_config(api_key=""), ["Sentence."], "voice", "API key is not configured"),
        (_config(endpoint=""), ["Sentence."], "voice", "endpoint is not configured"),
        (_config(batch_timeout_seconds=0), ["Sentence."], "voice", "timeout must be positive"),
        (_config(poll_interval_seconds=0), ["Sentence."], "voice", "interval must be positive"),
        (_config(), [], "voice", "sentences must not be empty"),
        (_config(), ["Sentence.", " \n "], "voice", "sentences must not be empty"),
        (_config(), ["Sentence."], " ", "voice is required"),
    ],
)
def test_synthesize_rejects_invalid_input(
    config: AppConfig,
    sentences: list[str],
    voice: str,
    message: str,
) -> None:
    provider = MicrosoftFoundrySpeechProvider(config)

    with pytest.raises(SpeechServiceError, match=message):
        provider.synthesize(sentences, voice)


def test_synthesize_rejects_request_larger_than_two_megabytes() -> None:
    provider = MicrosoftFoundrySpeechProvider(_config())

    with pytest.raises(SpeechServiceError, match="exceeds the 2 MB payload limit"):
        provider.synthesize(["x" * (2 * 1024 * 1024)], "en-US-JennyNeural")


def test_synthesize_retries_transient_poll_and_download_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archive = _result_zip(
        sentence_boundaries=[_boundary("Sentence.", 0, 500)],
        word_boundaries=[_boundary("Sentence.", 0, 500)],
    )
    counts = {"poll": 0, "download": 0, "delete": 0}
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "PUT":
            return httpx.Response(201, json={"status": "Running"})
        if request.method == "DELETE":
            counts["delete"] += 1
            return httpx.Response(500)
        if request.url.host == "results.example.test":
            counts["download"] += 1
            if counts["download"] == 1:
                return httpx.Response(503, json={"error": {"code": "Busy"}})
            return httpx.Response(200, content=archive)
        counts["poll"] += 1
        if counts["poll"] == 1:
            return httpx.Response(429, json={"error": {"code": "Throttled"}})
        return httpx.Response(
            200,
            json={
                "status": "Succeeded",
                "outputs": {"result": "https://results.example.test/results.zip"},
            },
        )

    monkeypatch.setattr(speech_module.time, "sleep", sleeps.append)

    artifact = _provider(handler).synthesize(["Sentence."], "en-US-JennyNeural")

    assert artifact.audio_data == _WAV_DATA
    assert counts == {"poll": 2, "download": 2, "delete": 1}
    assert sleeps == [1.0, 1.0, 1.0]


def test_synthesize_times_out_and_still_deletes_job(monkeypatch: pytest.MonkeyPatch) -> None:
    methods: list[str] = []
    monotonic_values = iter([0.0, 0.0, 2.0])

    def handler(request: httpx.Request) -> httpx.Response:
        methods.append(request.method)
        if request.method == "PUT":
            return httpx.Response(201, json={"status": "Running"})
        return httpx.Response(204)

    monkeypatch.setattr(speech_module.time, "monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr(speech_module.time, "sleep", lambda _seconds: None)

    with pytest.raises(SpeechServiceError, match="timed out after 1 seconds"):
        _provider(handler, config=_config(batch_timeout_seconds=1)).synthesize(
            ["Sentence."], "en-US-JennyNeural"
        )

    assert methods == ["PUT", "DELETE"]


def test_synthesize_surfaces_safe_failed_job_details(monkeypatch: pytest.MonkeyPatch) -> None:
    methods: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        methods.append(request.method)
        if request.method == "PUT":
            return httpx.Response(
                201,
                json={
                    "status": "Failed",
                    "properties": {
                        "error": {
                            "code": "InvalidVoice",
                            "message": " Voice was\nnot found. ",
                        }
                    },
                },
            )
        return httpx.Response(204)

    monkeypatch.setattr(speech_module.time, "sleep", lambda _seconds: None)

    with pytest.raises(
        SpeechServiceError,
        match="batch synthesis failed: InvalidVoice: Voice was not found",
    ):
        _provider(handler).synthesize(["Sentence."], "missing-voice")

    assert methods == ["PUT", "DELETE"]


@pytest.mark.parametrize(
    ("archive", "message"),
    [
        (b"not-a-zip", "invalid result ZIP"),
        (
            _result_zip(
                sentence_boundaries=[_boundary("Sentence.", 0, 500)],
                word_boundaries=[_boundary("Sentence.", 0, 500)],
                audio_data=b"not-wav-data",
            ),
            "invalid WAV file",
        ),
        (
            _result_zip(
                sentence_boundaries=[_boundary("Different.", 0, 500)],
                word_boundaries=[_boundary("Different.", 0, 500)],
            ),
            "do not align",
        ),
        (
            _result_zip(
                sentence_boundaries=[_boundary("Sentence.", 0, 500)],
                word_boundaries=[_boundary("Sentence.", 0, 500)],
                extra_files={"duplicate.wav": _WAV_DATA},
            ),
            "exactly one WAV file",
        ),
    ],
)
def test_synthesize_rejects_malformed_results(
    monkeypatch: pytest.MonkeyPatch,
    archive: bytes,
    message: str,
) -> None:
    calls: list[httpx.Request] = []
    monkeypatch.setattr(speech_module.time, "sleep", lambda _seconds: None)

    with pytest.raises(SpeechServiceError, match=message):
        _provider(_success_handler(archive, calls)).synthesize(
            ["Sentence."], "en-US-JennyNeural"
        )

    assert calls[-1].method == "DELETE"


def test_synthesize_rejects_overlapping_sentence_and_word_cues(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[httpx.Request] = []
    archive = _result_zip(
        sentence_boundaries=[
            _boundary("First.", 0, 700),
            _boundary("Second.", 600, 500),
        ],
        word_boundaries=[
            _boundary("First.", 0, 700),
            _boundary("Second.", 600, 500),
        ],
    )
    monkeypatch.setattr(speech_module.time, "sleep", lambda _seconds: None)

    with pytest.raises(SpeechServiceError, match="do not align"):
        _provider(_success_handler(archive, calls)).synthesize(
            ["First.", "Second."], "en-US-JennyNeural"
        )


def test_synthesize_wraps_create_transport_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    with pytest.raises(SpeechServiceError, match="batch synthesis failed") as error:
        _provider(handler).synthesize(["Sentence."], "en-US-JennyNeural")

    assert isinstance(error.value.__cause__, httpx.ConnectError)
