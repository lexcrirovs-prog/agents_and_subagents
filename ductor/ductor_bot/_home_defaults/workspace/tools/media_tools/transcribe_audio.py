#!/usr/bin/env python3
"""Transcribe audio/voice files to text.

Strategies (tried in order):
1. Local whisper.cpp server
2. Project-local Whisper bridge script
3. Local `whisper` CLI (Python package)
4. Local `whisper-cli` (whisper.cpp)
5. OpenAI Whisper API fallback

Usage:
    python tools/media_tools/transcribe_audio.py --file /path/to/audio.ogg
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

def _find_main_ductor_home() -> Path:
    candidates = [Path(__file__).resolve(), Path.cwd().resolve()]
    env_home = os.environ.get("DUCTOR_HOME")
    if env_home:
        candidates.append(Path(env_home).expanduser())

    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.name == "ductor-home" and resolved.parent.name == "runtime":
            return resolved
        for parent in resolved.parents:
            if parent.name == "ductor-home" and parent.parent.name == "runtime":
                return parent

    if env_home:
        return Path(env_home).expanduser().resolve()
    return (Path.home() / ".ductor").resolve()


_MAIN_DUCTOR_HOME = _find_main_ductor_home()
_PROJECT_ROOT = (
    _MAIN_DUCTOR_HOME.parent.parent
    if _MAIN_DUCTOR_HOME.parent.name == "runtime"
    else _MAIN_DUCTOR_HOME
)
_MEDIA_DIRS = (
    _MAIN_DUCTOR_HOME / "workspace" / "telegram_files",
    _MAIN_DUCTOR_HOME / "workspace" / "matrix_files",
    _MAIN_DUCTOR_HOME / "workspace" / "api_files",
)
_DEFAULT_TIMEOUT = int(os.environ.get("DUCTOR_WHISPER_TIMEOUT_SECONDS", "300"))
_DEFAULT_SERVER_BASE = os.environ.get(
    "DUCTOR_WHISPER_SERVER_URL",
    "http://127.0.0.1:8090",
).rstrip("/")
_DEFAULT_SERVER_ENDPOINT = f"{_DEFAULT_SERVER_BASE}/inference"
_DEFAULT_SCRIPT = Path(
    os.environ.get(
        "DUCTOR_WHISPER_SCRIPT",
        str(_PROJECT_ROOT / "scripts" / "transcribe-local-whisper.sh"),
    )
).expanduser()
_DEFAULT_MODEL = Path(
    os.environ.get(
        "DUCTOR_WHISPER_MODEL",
        str(Path.home() / "whisper.cpp" / "models" / "ggml-large-v3-turbo-q5_0.bin"),
    )
).expanduser()


def _load_default_language() -> str:
    configured = os.environ.get("DUCTOR_TRANSCRIBE_LANGUAGE", "").strip()
    if configured:
        return configured

    config_path = _MAIN_DUCTOR_HOME / "config" / "config.json"
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "auto"

    for key in ("voice_transcription_language", "language"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "auto"


_DEFAULT_LANGUAGE = _load_default_language()


def _normalize_transcript(text: str) -> str:
    return " ".join(text.split())


def _parse_whisper_payload(payload: str) -> tuple[str, str | None, float | None]:
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
                if isinstance(segment, dict):
                    part = segment.get("text")
                    if part:
                        parts.append(str(part))
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


def _transcribe_local_server(path: Path, language: str) -> dict:
    curl_bin = shutil.which("curl")
    if not curl_bin:
        return {"error": "curl not found"}

    ffmpeg_bin = shutil.which("ffmpeg")
    with tempfile.TemporaryDirectory(prefix="ductor-whisper-server-") as tmpdir:
        upload_path = path
        if ffmpeg_bin:
            wav_path = Path(tmpdir) / "input.wav"
            try:
                convert_result = subprocess.run(
                    [
                        ffmpeg_bin,
                        "-i",
                        str(path),
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
                    timeout=_DEFAULT_TIMEOUT,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                return {"error": f"ffmpeg conversion timed out after {_DEFAULT_TIMEOUT}s"}
            if convert_result.returncode != 0:
                return {"error": f"ffmpeg conversion failed: {convert_result.stderr[:500]}"}
            upload_path = wav_path

        cmd = [
            curl_bin,
            "-sS",
            "--max-time",
            str(_DEFAULT_TIMEOUT),
            "-X",
            "POST",
            _DEFAULT_SERVER_ENDPOINT,
            "-F",
            f"file=@{upload_path}",
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
                timeout=_DEFAULT_TIMEOUT + 5,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return {"error": f"whisper server timed out after {_DEFAULT_TIMEOUT}s"}

        if result.returncode != 0:
            return {"error": f"whisper server failed: {result.stderr[:500]}"}

        transcript, detected_language, duration = _parse_whisper_payload(result.stdout)
        if not transcript:
            return {"error": "whisper server returned an empty transcript"}

        return {
            "transcript": transcript,
            "language": detected_language or (None if language == "auto" else language),
            "duration_seconds": duration,
            "method": "local_whisper_server",
        }


def _transcribe_project_script(path: Path, language: str) -> dict:
    if not _DEFAULT_SCRIPT.exists():
        return {"error": f"project script not found: {_DEFAULT_SCRIPT}"}
    if not os.access(_DEFAULT_SCRIPT, os.X_OK):
        return {"error": f"project script is not executable: {_DEFAULT_SCRIPT}"}

    try:
        result = subprocess.run(
            [str(_DEFAULT_SCRIPT), str(path), language],
            capture_output=True,
            text=True,
            timeout=_DEFAULT_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"error": f"project whisper script timed out after {_DEFAULT_TIMEOUT}s"}

    if result.returncode != 0:
        detail = (result.stderr or result.stdout)[:500]
        return {"error": f"project whisper script failed: {detail}"}

    transcript = _normalize_transcript(result.stdout)
    if not transcript:
        return {"error": "project whisper script returned an empty transcript"}

    return {
        "transcript": transcript,
        "language": None if language == "auto" else language,
        "method": "project_whisper_script",
    }


def _transcribe_local_whisper(path: Path, language: str) -> dict:
    whisper_bin = shutil.which("whisper")
    if not whisper_bin:
        return {"error": "whisper CLI not found"}

    with tempfile.TemporaryDirectory(prefix="ductor-whisper-") as tmpdir:
        out_dir = Path(tmpdir)
        cmd = [
            whisper_bin,
            str(path),
            "--output_format",
            "json",
            "--output_dir",
            str(out_dir),
        ]
        if language != "auto":
            cmd.extend(["--language", language])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=_DEFAULT_TIMEOUT,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return {"error": f"whisper timed out after {_DEFAULT_TIMEOUT}s"}

        if result.returncode != 0:
            return {"error": f"whisper failed: {result.stderr[:500]}"}

        json_out = out_dir / f"{path.stem}.json"
        if json_out.exists():
            try:
                data = json.loads(json_out.read_text())
            except (json.JSONDecodeError, OSError) as exc:
                return {"error": f"failed to parse whisper JSON output: {exc}"}
            transcript = _normalize_transcript(str(data.get("text", "")))
            if not transcript:
                return {"error": "whisper returned an empty transcript"}
            return {
                "transcript": transcript,
                "language": data.get("language") or (None if language == "auto" else language),
                "method": "local_whisper",
            }

        transcript = _normalize_transcript(result.stdout)
        if not transcript:
            return {"error": "whisper returned an empty transcript"}
        return {
            "transcript": transcript,
            "language": None if language == "auto" else language,
            "method": "local_whisper",
        }


def _transcribe_whisper_cpp(path: Path, language: str) -> dict:
    whisper_cli = shutil.which("whisper-cli")
    if not whisper_cli:
        return {"error": "whisper-cli not found"}
    if not _DEFAULT_MODEL.exists():
        return {"error": f"whisper model not found: {_DEFAULT_MODEL}"}

    with tempfile.TemporaryDirectory(prefix="ductor-whispercpp-") as tmpdir:
        out_base = Path(tmpdir) / "transcript"
        cmd = [
            whisper_cli,
            "-m",
            str(_DEFAULT_MODEL),
            "-f",
            str(path),
            "--no-timestamps",
            "-otxt",
            "-of",
            str(out_base),
        ]
        if language != "auto":
            cmd.extend(["-l", language])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=_DEFAULT_TIMEOUT,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return {"error": f"whisper-cli timed out after {_DEFAULT_TIMEOUT}s"}

        if result.returncode != 0:
            return {"error": f"whisper-cli failed: {result.stderr[:500]}"}

        txt_out = out_base.with_suffix(".txt")
        if txt_out.exists():
            transcript = _normalize_transcript(txt_out.read_text())
            if transcript:
                return {
                    "transcript": transcript,
                    "language": None if language == "auto" else language,
                    "method": "whisper_cpp",
                }

        transcript = _normalize_transcript(result.stdout)
        if not transcript:
            return {"error": "whisper-cli returned an empty transcript"}
        return {
            "transcript": transcript,
            "language": None if language == "auto" else language,
            "method": "whisper_cpp",
        }


def _transcribe_openai(path: Path, language: str) -> dict:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return {"error": "OPENAI_API_KEY not set"}

    try:
        from openai import OpenAI  # type: ignore[import-untyped]
    except ImportError:
        return {"error": "openai package not installed (pip install openai)"}

    client = OpenAI(api_key=api_key)
    try:
        with path.open("rb") as file_obj:
            result = client.audio.transcriptions.create(
                model="whisper-1",
                file=file_obj,
                response_format="verbose_json",
                language=None if language == "auto" else language,
            )
    except Exception as exc:
        return {"error": f"OpenAI API error: {exc}"}

    transcript = _normalize_transcript(result.text)
    if not transcript:
        return {"error": "OpenAI Whisper returned an empty transcript"}

    return {
        "transcript": transcript,
        "language": getattr(result, "language", None) or (None if language == "auto" else language),
        "duration_seconds": getattr(result, "duration", None),
        "method": "openai_whisper_api",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Transcribe audio/voice to text")
    parser.add_argument("--file", required=True, help="Path to audio file")
    parser.add_argument(
        "--language",
        default=_DEFAULT_LANGUAGE,
        help=f"Language hint for transcription (default: {_DEFAULT_LANGUAGE})",
    )
    args = parser.parse_args()

    path = Path(args.file).expanduser().resolve()
    if not any(path.is_relative_to(d.resolve()) for d in _MEDIA_DIRS if d.exists()):
        print(json.dumps({"error": f"Path outside media directories: {path}"}))
        sys.exit(1)
    if not path.exists():
        print(json.dumps({"error": f"File not found: {path}"}))
        sys.exit(1)

    strategies = [
        _transcribe_local_server,
        _transcribe_project_script,
        _transcribe_local_whisper,
        _transcribe_whisper_cpp,
        _transcribe_openai,
    ]
    errors: list[str] = []

    for strategy in strategies:
        result = strategy(path, args.language)
        if "transcript" in result:
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return
        errors.append(result.get("error", "unknown error"))

    print(
        json.dumps(
            {
                "error": "All transcription methods failed",
                "details": errors,
                "hint": (
                    "Check the local whisper.cpp server at "
                    f"{_DEFAULT_SERVER_ENDPOINT}, the project bridge script "
                    f"{_DEFAULT_SCRIPT}, or install a local whisper CLI/OpenAI fallback."
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
