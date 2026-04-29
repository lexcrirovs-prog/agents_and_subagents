"""Helpers for locating the internal localhost API from runtime tool scripts."""

from __future__ import annotations

import json
import os
from pathlib import Path

from _runtime_paths import resolve_main_ductor_home

_DEFAULT_PORT = 8799


def _parse_port(raw: str | None) -> int | None:
    try:
        port = int(str(raw or "").strip())
    except ValueError:
        return None
    return port if 0 < port < 65536 else None


def resolve_internal_api_host() -> str:
    """Resolve the current internal API host."""
    host = os.environ.get("DUCTOR_INTERAGENT_HOST", "").strip()
    return host or "127.0.0.1"


def _load_port_file(home: Path) -> int | None:
    port_file = home / "internal_api_port.txt"
    if not port_file.is_file():
        return None
    try:
        return _parse_port(port_file.read_text(encoding="utf-8"))
    except OSError:
        return None


def _load_config_port(home: Path) -> int | None:
    config_path = home / "config" / "config.json"
    if not config_path.is_file():
        return None
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return _parse_port(str(data.get("interagent_port", "")))


def resolve_internal_api_port() -> int:
    """Resolve the internal API port from env, port hint, config, or default."""
    env_port = _parse_port(os.environ.get("DUCTOR_INTERAGENT_PORT"))
    if env_port is not None:
        return env_port

    home = resolve_main_ductor_home()
    port = _load_port_file(home)
    if port is not None:
        return port

    port = _load_config_port(home)
    if port is not None:
        return port

    return _DEFAULT_PORT


def build_internal_api_url(path: str) -> str:
    """Build a full localhost URL for an internal API path."""
    normalized = path if path.startswith("/") else f"/{path}"
    return f"http://{resolve_internal_api_host()}:{resolve_internal_api_port()}{normalized}"
