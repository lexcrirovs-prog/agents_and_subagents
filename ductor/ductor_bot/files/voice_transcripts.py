"""Fast cached ingress transcription for Telegram voice notes."""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import tempfile
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from ductor_bot.files.prompt import MediaInfo

logger = logging.getLogger(__name__)

_FAST_TIMEOUT_SECONDS = int(os.environ.get("DUCTOR_FAST_VOICE_TIMEOUT_SECONDS", "12"))
_INLINE_LIMIT = int(os.environ.get("DUCTOR_FAST_VOICE_INLINE_CHARS", "4000"))
_DEFAULT_SERVER_BASE = os.environ.get(
    "DUCTOR_WHISPER_SERVER_URL",
    "http://127.0.0.1:8090",
).rstrip("/")
_DEFAULT_SERVER_ENDPOINT = f"{_DEFAULT_SERVER_BASE}/inference"
_DEFAULT_LANGUAGE = os.environ.get("DUCTOR_FAST_VOICE_LANGUAGE", "auto").strip() or "auto"


def transcript_sidecar_path(audio_path: Path) -> Path:
    """Return the hidden sidecar path used for cached voice transcripts."""
    return audio_path.with_name(f".{audio_path.name}.transcript.json")


def hydrate_voice_transcript(
    info: MediaInfo,
    *,
    preferred_language: str | None = None,
) -> MediaInfo:
    """Attach a cached fast transcript to Telegram voice messages when available."""
    if info.original_type != "voice":
        return info

    language = _resolve_language(preferred_language)
    payload = load_cached_transcript(info.path)
    if payload is None or _cached_transcript_needs_refresh(payload, language):
        payload = _transcribe_fast(info.path, language)
        if payload is None:
            return info
        _write_cached_transcript(info.path, payload)

    transcript = str(payload.get("transcript", "")).strip()
    if not transcript:
        return info

    return replace(
        info,
        transcript_text=_truncate_inline_transcript(transcript),
        transcript_path=transcript_sidecar_path(info.path),
        transcript_method=str(payload.get("method", "local_whisper_server")),
    )


def load_cached_transcript(audio_path: Path) -> dict[str, object] | None:
    """Load a cached transcript when the sidecar is newer than the audio file."""
    sidecar = transcript_sidecar_path(audio_path)
    try:
        if not sidecar.exists():
            return None
        if sidecar.stat().st_mtime < audio_path.stat().st_mtime:
            return None
        data = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.debug("Ignoring unreadable transcript cache for %s", audio_path, exc_info=True)
        return None

    transcript = data.get("transcript")
    if not isinstance(transcript, str) or not transcript.strip():
        return None
    return data


def _truncate_inline_transcript(text: str) -> str:
    if len(text) <= _INLINE_LIMIT:
        return text
    return text[: _INLINE_LIMIT - 1].rstrip() + "…"


def _write_cached_transcript(audio_path: Path, payload: dict[str, object]) -> None:
    sidecar = transcript_sidecar_path(audio_path)
    data = {
        "audio_file": audio_path.name,
        "created_at": datetime.now(tz=UTC).isoformat(),
        "mode": "fast_ingress",
        **payload,
    }
    try:
        sidecar.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        logger.debug("Failed to write transcript cache for %s", audio_path, exc_info=True)


def _normalize_transcript(text: str) -> str:
    return " ".join(text.split())


def _resolve_language(preferred_language: str | None) -> str:
    candidate = (preferred_language or "").strip().lower()
    if candidate:
        return candidate
    return _DEFAULT_LANGUAGE.lower()


def _cached_transcript_needs_refresh(payload: dict[str, object], preferred_language: str) -> bool:
    if preferred_language == "auto":
        return False
    cached_language = str(payload.get("language") or "").strip().lower()
    return cached_language != preferred_language


def _parse_payload(payload: str) -> tuple[str, str | None, float | None]:
    raw = payload.strip()
    if not raw:
        return "", None, None

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return _normalize_transcript(raw), None, None

    if isinstance(data, dict):
        text = data.get("text") or data.get("transcript") or ""
        if not text and isinstance(data.get("segments"), list):
            parts = []
            for segment in data["segments"]:
                if isinstance(segment, dict) and segment.get("text"):
                    parts.append(str(segment["text"]))
            text = " ".join(parts)
        return (
            _normalize_transcript(str(text)),
            data.get("language"),
            data.get("duration"),
        )

    if isinstance(data, list):
        parts = []
        for item in data:
            if isinstance(item, dict) and item.get("text"):
                parts.append(str(item["text"]))
        return _normalize_transcript(" ".join(parts)), None, None

    return _normalize_transcript(str(data)), None, None


def _transcribe_fast(audio_path: Path, language: str) -> dict[str, object] | None:
    curl_bin = shutil.which("curl")
    ffmpeg_bin = shutil.which("ffmpeg")
    if not curl_bin or not ffmpeg_bin:
        logger.debug("Fast voice ingress is unavailable: curl=%s ffmpeg=%s", curl_bin, ffmpeg_bin)
        return None

    with tempfile.TemporaryDirectory(prefix="ductor-voice-fast-") as tmpdir:
        wav_path = Path(tmpdir) / "input.wav"
        try:
            convert_result = subprocess.run(
                [
                    ffmpeg_bin,
                    "-i",
                    str(audio_path),
                    "-ar",
                    "16000",
                    "-ac",
                    "1",
                    "-c:a",
                    "pcm_s16le",
                    str(wav_path),
                    "-y",
                    "-loglevel",
                    "error",
                ],
                capture_output=True,
                text=True,
                timeout=_FAST_TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired:
            logger.debug("Fast voice conversion timed out for %s", audio_path)
            return None

        if convert_result.returncode != 0:
            logger.debug(
                "Fast voice conversion failed for %s: %s",
                audio_path,
                convert_result.stderr[:300],
            )
            return None

        cmd = [
            curl_bin,
            "-sS",
            "--max-time",
            str(_FAST_TIMEOUT_SECONDS),
            "-X",
            "POST",
            _DEFAULT_SERVER_ENDPOINT,
            "-F",
            f"file=@{wav_path}",
            "-F",
            "temperature=0.0",
            "-F",
            "response_format=json",
        ]
        if language != "auto":
            cmd.extend(["-F", f"language={language}"])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=_FAST_TIMEOUT_SECONDS + 3,
                check=False,
            )
        except subprocess.TimeoutExpired:
            logger.debug("Fast voice server timed out for %s", audio_path)
            return None

        if result.returncode != 0:
            logger.debug(
                "Fast voice server failed for %s: %s",
                audio_path,
                result.stderr[:300],
            )
            return None

        transcript, detected_language, duration = _parse_payload(result.stdout)
        if not transcript:
            logger.debug("Fast voice server returned an empty transcript for %s", audio_path)
            return None

        return {
            "transcript": transcript,
            "language": detected_language or (None if language == "auto" else language),
            "duration_seconds": duration,
            "method": "local_whisper_server",
        }
