"""Transport-agnostic media prompt building."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class MediaInfo:
    """Metadata for a received media file (from any transport)."""

    caption: str | None
    file_name: str
    media_type: str
    original_type: str
    path: Path
    transcript_method: str | None = None
    transcript_path: Path | None = None
    transcript_text: str | None = None


def build_media_prompt(
    info: MediaInfo,
    workspace: Path,
    *,
    transport: str = "",
) -> str:
    """Build the prompt injected into the orchestrator for a received file.

    Paths are relative to *workspace* so they work in both host and Docker.
    """
    rel_path = _relative_path_or_self(info.path, workspace)

    via = f" via {transport}" if transport else ""
    lines = [
        "[INCOMING FILE]",
        f"The user sent you a file{via}.",
        f"Path: {rel_path}",
        f"Type: {info.media_type}",
        f"Original filename: {info.file_name}",
        "",
        "Check tools/media_tools/RULES.md for file handling instructions.",
    ]

    if info.original_type in ("voice", "audio") and info.transcript_text:
        lines.append(
            "A cached transcript is already attached below. Use it as the primary content. "
            "Treat it as the user's message and reply to its meaning directly. "
            "Do not just restate the transcript unless the user explicitly asks for the transcription "
            "or the audio is ambiguous. Only re-run transcription if it looks wrong or the user "
            "explicitly asks for a more exact pass."
        )
        if info.transcript_path:
            lines.append(f"Transcript cache: {_relative_path_or_self(info.transcript_path, workspace)}")
        if info.transcript_method:
            lines.append(f"Transcript method: {info.transcript_method}")
        lines.append("")
        lines.append("[AUDIO TRANSCRIPT]")
        lines.append(info.transcript_text)
    elif info.original_type in ("voice", "audio"):
        lines.append(
            "This is an audio/voice message. Use "
            f"tools/media_tools/transcribe_audio.py --file {rel_path} "
            "to transcribe it with the local Whisper contour first, then reply to the meaning of "
            "the user's message. Do not stop at reporting the transcript."
        )

    if info.original_type in ("video", "video_note"):
        lines.append(
            "This is a video file. Use "
            f"tools/media_tools/process_video.py --file {rel_path} "
            "to extract keyframes and transcribe audio, then respond to the content."
        )

    if info.caption:
        lines.append("")
        lines.append(f"User message: {info.caption}")

    return "\n".join(lines)


def _relative_path_or_self(path: Path, workspace: Path) -> Path | str:
    rel_path: Path | str = path
    with contextlib.suppress(ValueError):
        rel_path = path.relative_to(workspace)
    return rel_path
