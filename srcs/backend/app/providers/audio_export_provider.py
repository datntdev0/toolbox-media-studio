"""Audio export provider for concatenating sentence audio files."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import httpx


class AudioExportError(RuntimeError):
    """Raised when audio files cannot be concatenated."""


class AudioExportProvider:
    """Concatenates audio files using FFmpeg."""

    def __init__(self) -> None:
        self._http_client = httpx.Client(timeout=30.0)

    def concatenate_audio_files(self, audio_urls: list[str]) -> bytes:
        """
        Download audio files from URLs and concatenate them using FFmpeg.

        Args:
            audio_urls: List of public URLs to WAV audio files in order.

        Returns:
            Concatenated WAV file as bytes.

        Raises:
            AudioExportError: If download or concatenation fails.
        """
        if not audio_urls:
            raise AudioExportError("No audio URLs provided for concatenation")

        temp_dir = Path(tempfile.mkdtemp(prefix="audio_export_"))
        try:
            # Download all audio files
            audio_files: list[Path] = []
            for index, url in enumerate(audio_urls):
                try:
                    response = self._http_client.get(url)
                    response.raise_for_status()
                    audio_path = temp_dir / f"audio_{index:04d}.wav"
                    audio_path.write_bytes(response.content)
                    audio_files.append(audio_path)
                except Exception as exc:
                    raise AudioExportError(
                        f"Failed to download audio file {index} from {url}"
                    ) from exc

            # Create FFmpeg concat file list
            concat_list_path = temp_dir / "concat_list.txt"
            concat_list_path.write_text(
                "\n".join(f"file '{audio_file.name}'" for audio_file in audio_files),
                encoding="utf-8",
            )

            # Concatenate using FFmpeg
            output_path = temp_dir / "output.wav"
            try:
                subprocess.run(
                    [
                        "ffmpeg",
                        "-f",
                        "concat",
                        "-safe",
                        "0",
                        "-i",
                        str(concat_list_path),
                        "-c",
                        "copy",
                        str(output_path),
                    ],
                    cwd=str(temp_dir),
                    check=True,
                    capture_output=True,
                    text=True,
                )
            except subprocess.CalledProcessError as exc:
                raise AudioExportError(
                    f"FFmpeg concatenation failed: {exc.stderr}"
                ) from exc
            except FileNotFoundError as exc:
                raise AudioExportError(
                    "FFmpeg is not installed or not available in PATH"
                ) from exc

            if not output_path.exists():
                raise AudioExportError("FFmpeg did not produce output file")

            return output_path.read_bytes()

        finally:
            # Clean up temporary directory
            for file_path in temp_dir.iterdir():
                try:
                    file_path.unlink()
                except Exception:
                    pass
            try:
                temp_dir.rmdir()
            except Exception:
                pass


def build_audio_export_provider() -> AudioExportProvider:
    """Build the audio export provider singleton."""
    return AudioExportProvider()
