"""Local runtime-home discovery for deployed workspace tools.

These scripts are often executed directly from a runtime workspace, outside the
bot process and without ``DUCTOR_HOME``/``PYTHONPATH`` preconfigured. The
helpers below resolve the active runtime from either the environment, the
script location, or the current working directory.
"""

from __future__ import annotations

import os
from pathlib import Path


def _iter_candidates() -> list[Path]:
    candidates: list[Path] = []
    env_home = os.environ.get("DUCTOR_HOME", "").strip()
    if env_home:
        candidates.append(Path(env_home).expanduser())
    candidates.append(Path(__file__).resolve())
    candidates.append(Path.cwd().resolve())
    return candidates


def _resolve_home_from_candidate(candidate: Path) -> Path | None:
    current = candidate if candidate.is_dir() else candidate.parent
    for parent in (current, *current.parents):
        if (parent / "config" / "config.json").is_file() and (parent / "workspace").is_dir():
            return parent.resolve()
        if parent.name == "workspace" and (parent.parent / "config" / "config.json").is_file():
            return parent.parent.resolve()
    return None


def resolve_ductor_home() -> Path:
    """Resolve the current agent's runtime home."""
    for candidate in _iter_candidates():
        resolved = _resolve_home_from_candidate(candidate)
        if resolved is not None:
            return resolved

    env_home = os.environ.get("DUCTOR_HOME", "").strip()
    if env_home:
        return Path(env_home).expanduser().resolve()
    return (Path.home() / ".ductor").resolve()


def resolve_main_ductor_home() -> Path:
    """Resolve the main runtime home, even when called inside a sub-agent."""
    home = resolve_ductor_home()
    if home.parent.name == "agents":
        return home.parent.parent.resolve()
    return home
