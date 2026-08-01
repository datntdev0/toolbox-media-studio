"""Microsoft Foundry Speech provider for in-memory text-to-speech synthesis."""

from __future__ import annotations

from threading import Event
from typing import Any, Protocol

import azure.cognitiveservices.speech as speechsdk  # type: ignore[import-untyped]

from app.core.config.app_config import AppConfig


class SpeechServiceError(RuntimeError):
    """Raised when a speech service cannot synthesize audio."""


class SpeechServiceProvider(Protocol):
    """Contract implemented by a text-to-speech service."""

    def synthesize(self, text: str, voice: str) -> bytes: ...


class MicrosoftFoundrySpeechProvider:
    """Text-to-speech provider backed by Microsoft Foundry Speech."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config

    def synthesize(self, text: str, voice: str) -> bytes:
        """Synthesize one sentence as a RIFF 24 kHz, 16-bit mono PCM WAV."""

        api_key = self._config.azure_speech.api_key
        endpoint = self._config.azure_speech.endpoint
        timeout_seconds = self._config.azure_speech.timeout_seconds
        if not api_key:
            raise SpeechServiceError("Azure Speech API key is not configured")
        if not endpoint:
            raise SpeechServiceError("Azure Speech endpoint is not configured")
        if timeout_seconds <= 0:
            raise SpeechServiceError("Azure Speech timeout must be positive")

        try:
            speech_config = speechsdk.SpeechConfig(subscription=api_key, endpoint=endpoint)
            speech_config.speech_synthesis_voice_name = voice
            speech_config.set_speech_synthesis_output_format(
                speechsdk.SpeechSynthesisOutputFormat.Riff24Khz16BitMonoPcm
            )
            synthesizer = speechsdk.SpeechSynthesizer(
                speech_config=speech_config,
                audio_config=None,
            )
            completed = Event()
            results: list[Any] = []

            def complete(event: Any) -> None:
                if completed.is_set():
                    return
                results.append(event.result)
                completed.set()

            synthesizer.synthesis_completed.connect(complete)
            synthesizer.synthesis_canceled.connect(complete)
            try:
                _future = synthesizer.speak_text_async(text)
                if not completed.wait(timeout_seconds):
                    synthesizer.stop_speaking_async()
                    raise SpeechServiceError(
                        f"Azure Speech synthesis timed out after {timeout_seconds} seconds"
                    )
                if not results:
                    raise SpeechServiceError("Azure Speech synthesis completed without a result")
                result = results[0]
            finally:
                synthesizer.synthesis_completed.disconnect_all()
                synthesizer.synthesis_canceled.disconnect_all()

            if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
                cancellation = result.cancellation_details
                details = cancellation.error_details if cancellation is not None else ""
                reason = cancellation.reason if cancellation is not None else result.reason
                message = f"Azure Speech synthesis was canceled: {reason}"
                if details:
                    message = f"{message}: {details}"
                raise SpeechServiceError(message)

            audio_data = bytes(result.audio_data)
            if not audio_data:
                raise SpeechServiceError("Azure Speech returned empty audio")
            return audio_data
        except SpeechServiceError:
            raise
        except Exception as exc:
            raise SpeechServiceError("Azure Speech synthesis failed") from exc


def build_speech_service_provider(config: AppConfig) -> MicrosoftFoundrySpeechProvider:
    """Construct a provider without requiring Speech configuration at startup."""

    return MicrosoftFoundrySpeechProvider(config)
