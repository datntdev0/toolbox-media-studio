"""Microsoft Foundry Speech provider for chapter-level batch synthesis."""

from __future__ import annotations

import io
import json
import math
import re
import time
import unicodedata
import uuid
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol, TypeGuard, cast

import httpx

from app.core.config.app_config import AppConfig

_API_VERSION = "2024-04-01"
_MAX_REQUEST_BYTES = 2 * 1024 * 1024
_REQUEST_TIMEOUT_SECONDS = 30.0
_MAX_TRANSIENT_ATTEMPTS = 3
_TRANSIENT_STATUS_CODES = frozenset({408, 429, 500, 502, 503, 504})
_PENDING_STATUSES = frozenset({"NotStarted", "Running"})


class SpeechServiceError(RuntimeError):
    """Raised when a speech service cannot synthesize audio and subtitles."""


@dataclass(frozen=True)
class SpeechSynthesisArtifact:
    """Chapter-level audio and subtitle files returned by a speech service."""

    audio_data: bytes
    subtitle_data: bytes


class SpeechServiceProvider(Protocol):
    """Contract implemented by a text-to-speech service."""

    def synthesize(self, sentences: list[str], voice: str) -> SpeechSynthesisArtifact: ...


@dataclass(frozen=True)
class _Boundary:
    text: str
    audio_offset_ms: float
    duration_ms: float

    @property
    def end_ms(self) -> float:
        return self.audio_offset_ms + self.duration_ms


class MicrosoftFoundrySpeechProvider:
    """Chapter-level text-to-speech provider backed by Azure Batch Synthesis."""

    def __init__(
        self,
        config: AppConfig,
        *,
        client_factory: Callable[[], httpx.Client] | None = None,
    ) -> None:
        self._config = config
        self._client_factory = client_factory or (
            lambda: httpx.Client(timeout=_REQUEST_TIMEOUT_SECONDS)
        )

    def synthesize(self, sentences: list[str], voice: str) -> SpeechSynthesisArtifact:
        """Synthesize a chapter into one WAV and one sentence-aligned SRT file."""

        settings = self._config.azure_speech
        api_key = settings.api_key
        endpoint = settings.endpoint.rstrip("/")
        timeout_seconds = settings.batch_timeout_seconds
        poll_interval_seconds = settings.poll_interval_seconds
        if not api_key:
            raise SpeechServiceError("Azure Speech API key is not configured")
        if not endpoint:
            raise SpeechServiceError("Azure Speech endpoint is not configured")
        if timeout_seconds <= 0:
            raise SpeechServiceError("Azure Speech batch timeout must be positive")
        if poll_interval_seconds <= 0:
            raise SpeechServiceError("Azure Speech poll interval must be positive")
        if not voice.strip():
            raise SpeechServiceError("Azure Speech voice is required")

        normalized_sentences = [_normalize_display_text(sentence) for sentence in sentences]
        if not normalized_sentences or any(not sentence for sentence in normalized_sentences):
            raise SpeechServiceError("Azure Speech sentences must not be empty")

        payload = {
            "inputKind": "PlainText",
            "inputs": [{"content": "\r\n".join(normalized_sentences)}],
            "synthesisConfig": {"voice": voice.strip()},
            "properties": {
                "outputFormat": "riff-24khz-16bit-mono-pcm",
                "wordBoundaryEnabled": True,
                "sentenceBoundaryEnabled": True,
                "concatenateResult": True,
                "decompressOutputFiles": False,
            },
        }
        request_body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
        if len(request_body) > _MAX_REQUEST_BYTES:
            raise SpeechServiceError("Azure Speech batch request exceeds the 2 MB payload limit")

        job_id = f"speech-{uuid.uuid4().hex}"
        job_url = f"{endpoint}/texttospeech/batchsyntheses/{job_id}"
        headers = {
            "Ocp-Apim-Subscription-Key": api_key,
            "Content-Type": "application/json",
        }
        job_created = False
        try:
            with self._client_factory() as client:
                response = client.put(
                    job_url,
                    params={"api-version": _API_VERSION},
                    headers=headers,
                    content=request_body,
                )
                _raise_for_response(response, "create batch synthesis")
                job_created = True
                job = _response_json_object(response, "create batch synthesis")
                completed_job = self._wait_for_completion(
                    client,
                    job_url=job_url,
                    headers=headers,
                    initial_job=job,
                    timeout_seconds=timeout_seconds,
                    poll_interval_seconds=poll_interval_seconds,
                )
                result_url = _result_url(completed_job)
                result = self._request_with_retries(
                    client,
                    "GET",
                    result_url,
                    headers={"Ocp-Apim-Subscription-Key": api_key},
                    poll_interval_seconds=poll_interval_seconds,
                    operation="download batch synthesis results",
                )
                return _artifact_from_zip(result.content, normalized_sentences)
        except SpeechServiceError:
            raise
        except Exception as exc:
            raise SpeechServiceError("Azure Speech batch synthesis failed") from exc
        finally:
            if job_created:
                self._delete_job(job_url, headers)

    def _wait_for_completion(
        self,
        client: httpx.Client,
        *,
        job_url: str,
        headers: dict[str, str],
        initial_job: dict[str, Any],
        timeout_seconds: int,
        poll_interval_seconds: int,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout_seconds
        job = initial_job
        while True:
            status = job.get("status")
            if status == "Succeeded":
                return job
            if status == "Failed":
                details = _job_error_details(job)
                message = "Azure Speech batch synthesis failed"
                if details:
                    message = f"{message}: {details}"
                raise SpeechServiceError(message)
            if status not in _PENDING_STATUSES:
                raise SpeechServiceError(
                    f"Azure Speech returned an unexpected batch status: {_safe_text(status)}"
                )

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise SpeechServiceError(
                    f"Azure Speech batch synthesis timed out after {timeout_seconds} seconds"
                )
            time.sleep(min(float(poll_interval_seconds), remaining))
            if time.monotonic() >= deadline:
                raise SpeechServiceError(
                    f"Azure Speech batch synthesis timed out after {timeout_seconds} seconds"
                )
            response = self._request_with_retries(
                client,
                "GET",
                job_url,
                params={"api-version": _API_VERSION},
                headers=headers,
                poll_interval_seconds=poll_interval_seconds,
                operation="poll batch synthesis",
            )
            job = _response_json_object(response, "poll batch synthesis")

    def _request_with_retries(
        self,
        client: httpx.Client,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        poll_interval_seconds: int,
        operation: str,
        params: dict[str, str] | None = None,
    ) -> httpx.Response:
        last_transport_error: httpx.RequestError | None = None
        for attempt in range(_MAX_TRANSIENT_ATTEMPTS):
            try:
                response = client.request(method, url, params=params, headers=headers)
            except httpx.RequestError as exc:
                last_transport_error = exc
            else:
                if response.status_code not in _TRANSIENT_STATUS_CODES:
                    _raise_for_response(response, operation)
                    return response
                if attempt == _MAX_TRANSIENT_ATTEMPTS - 1:
                    _raise_for_response(response, operation)
            if attempt < _MAX_TRANSIENT_ATTEMPTS - 1:
                time.sleep(float(poll_interval_seconds))

        raise SpeechServiceError(f"Azure Speech could not {operation}") from last_transport_error

    def _delete_job(self, job_url: str, headers: dict[str, str]) -> None:
        try:
            with self._client_factory() as client:
                client.delete(
                    job_url,
                    params={"api-version": _API_VERSION},
                    headers=headers,
                )
        except Exception:
            # The job expires server-side; cleanup must not mask synthesis failures or artifacts.
            pass


def _artifact_from_zip(data: bytes, sentences: list[str]) -> SpeechSynthesisArtifact:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = [info.filename for info in archive.infolist() if not info.is_dir()]
            wav_name = _single_result_name(names, ".wav", "WAV")
            sentence_name = _single_result_name(names, ".sentence.json", "sentence boundary")
            word_name = _single_result_name(names, ".word.json", "word boundary")
            audio_data = archive.read(wav_name)
            sentence_data = archive.read(sentence_name)
            word_data = archive.read(word_name)
    except SpeechServiceError:
        raise
    except (KeyError, OSError, zipfile.BadZipFile) as exc:
        raise SpeechServiceError("Azure Speech returned an invalid result ZIP") from exc

    if len(audio_data) < 12 or audio_data[:4] != b"RIFF" or audio_data[8:12] != b"WAVE":
        raise SpeechServiceError("Azure Speech result ZIP contains an invalid WAV file")

    sentence_boundaries = _parse_boundaries(sentence_data, "sentence")
    word_boundaries = _parse_boundaries(word_data, "word")
    cues = _match_sentence_boundaries(sentences, sentence_boundaries)
    if cues is None:
        cues = _match_word_boundaries(sentences, word_boundaries)
    if cues is None:
        raise SpeechServiceError("Azure Speech boundaries do not align with chapter sentences")

    return SpeechSynthesisArtifact(
        audio_data=audio_data,
        subtitle_data=_render_srt(sentences, cues).encode("utf-8"),
    )


def _single_result_name(names: list[str], suffix: str, label: str) -> str:
    matches = [name for name in names if name.lower().endswith(suffix)]
    if len(matches) != 1:
        raise SpeechServiceError(
            f"Azure Speech result ZIP must contain exactly one {label} file"
        )
    return matches[0]


def _parse_boundaries(data: bytes, label: str) -> list[_Boundary]:
    try:
        value = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SpeechServiceError(f"Azure Speech returned invalid {label} boundary JSON") from exc
    if not isinstance(value, list) or not value:
        raise SpeechServiceError(f"Azure Speech returned invalid {label} boundary JSON")

    boundaries: list[_Boundary] = []
    for item in value:
        if not isinstance(item, dict):
            raise SpeechServiceError(f"Azure Speech returned invalid {label} boundary JSON")
        text = item.get("Text")
        audio_offset = item.get("AudioOffset")
        duration = item.get("Duration")
        if (
            not isinstance(text, str)
            or not text
            or not _is_nonnegative_number(audio_offset)
            or not _is_nonnegative_number(duration)
        ):
            raise SpeechServiceError(f"Azure Speech returned invalid {label} boundary JSON")
        boundaries.append(
            _Boundary(
                text=text,
                audio_offset_ms=float(audio_offset),
                duration_ms=float(duration),
            )
        )
    return boundaries


def _is_nonnegative_number(value: object) -> TypeGuard[int | float]:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value >= 0
    )


def _match_sentence_boundaries(
    sentences: list[str], boundaries: list[_Boundary]
) -> list[_Boundary] | None:
    if len(sentences) != len(boundaries):
        return None
    if any(
        _canonical_text(sentence) != _canonical_text(boundary.text)
        for sentence, boundary in zip(sentences, boundaries, strict=True)
    ):
        return None
    if not _valid_cue_timings(boundaries):
        return None
    return boundaries


def _match_word_boundaries(
    sentences: list[str], boundaries: list[_Boundary]
) -> list[_Boundary] | None:
    cues: list[_Boundary] = []
    word_index = 0
    for sentence in sentences:
        target = _canonical_text(sentence)
        combined = ""
        first_boundary: _Boundary | None = None
        last_boundary: _Boundary | None = None
        while word_index < len(boundaries) and len(combined) < len(target):
            boundary = boundaries[word_index]
            candidate = combined + _canonical_text(boundary.text)
            if not target.startswith(candidate):
                return None
            if first_boundary is None:
                first_boundary = boundary
            last_boundary = boundary
            combined = candidate
            word_index += 1
        if combined != target or first_boundary is None or last_boundary is None:
            return None
        cues.append(
            _Boundary(
                text=sentence,
                audio_offset_ms=first_boundary.audio_offset_ms,
                duration_ms=last_boundary.end_ms - first_boundary.audio_offset_ms,
            )
        )
    if word_index != len(boundaries) or not _valid_cue_timings(cues):
        return None
    return cues


def _valid_cue_timings(cues: list[_Boundary]) -> bool:
    previous_end = 0.0
    for cue in cues:
        if cue.audio_offset_ms < previous_end or cue.end_ms <= cue.audio_offset_ms:
            return False
        previous_end = cue.end_ms
    return True


def _render_srt(sentences: list[str], cues: list[_Boundary]) -> str:
    blocks = [
        f"{index}\r\n{_srt_timestamp(cue.audio_offset_ms)} --> "
        f"{_srt_timestamp(cue.end_ms)}\r\n{sentence}"
        for index, (sentence, cue) in enumerate(zip(sentences, cues, strict=True), start=1)
    ]
    return "\r\n\r\n".join(blocks) + "\r\n"


def _srt_timestamp(milliseconds: float) -> str:
    total_ms = max(0, round(milliseconds))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1_000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def _normalize_display_text(text: str) -> str:
    return " ".join(text.split())


def _canonical_text(text: str) -> str:
    normalized = unicodedata.normalize("NFC", text)
    return re.sub(r"\s+", "", normalized)


def _result_url(job: dict[str, Any]) -> str:
    outputs = job.get("outputs")
    if not isinstance(outputs, dict):
        raise SpeechServiceError("Azure Speech batch result URL is missing")
    result = outputs.get("result")
    if not isinstance(result, str) or not result.startswith(("https://", "http://")):
        raise SpeechServiceError("Azure Speech batch result URL is missing")
    return result


def _response_json_object(response: httpx.Response, operation: str) -> dict[str, Any]:
    try:
        value = response.json()
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise SpeechServiceError(
            f"Azure Speech returned invalid JSON while trying to {operation}"
        ) from exc
    if not isinstance(value, dict):
        raise SpeechServiceError(f"Azure Speech returned invalid JSON while trying to {operation}")
    return cast(dict[str, Any], value)


def _raise_for_response(response: httpx.Response, operation: str) -> None:
    if response.is_success:
        return
    details = _response_error_details(response)
    message = f"Azure Speech could not {operation} (HTTP {response.status_code})"
    if details:
        message = f"{message}: {details}"
    raise SpeechServiceError(message)


def _response_error_details(response: httpx.Response) -> str:
    try:
        value = response.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        return ""
    if not isinstance(value, dict):
        return ""
    error = value.get("error")
    return _error_details(error)


def _job_error_details(job: dict[str, Any]) -> str:
    properties = job.get("properties")
    if not isinstance(properties, dict):
        return ""
    return _error_details(properties.get("error"))


def _error_details(error: object) -> str:
    if not isinstance(error, dict):
        return ""
    code = _optional_safe_text(error.get("code"))
    message = _optional_safe_text(error.get("message"))
    if code and message:
        return f"{code}: {message}"
    return code or message


def _safe_text(value: object) -> str:
    return _optional_safe_text(value) or "unknown"


def _optional_safe_text(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())[:500]


def build_speech_service_provider(config: AppConfig) -> MicrosoftFoundrySpeechProvider:
    """Construct a provider without requiring Speech configuration at startup."""

    return MicrosoftFoundrySpeechProvider(config)
