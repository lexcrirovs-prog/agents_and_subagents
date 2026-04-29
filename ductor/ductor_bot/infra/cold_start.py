"""Cold-start smoke helpers for fresh runtime provisioning."""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from ductor_bot.config import DEFAULT_EMPTY_GEMINI_API_KEY, AgentConfig, deep_merge_config
from ductor_bot.infra.json_store import atomic_json_save
from ductor_bot.infra.preflight import PreflightReport, run_runtime_preflight
from ductor_bot.workspace.init import init_workspace
from ductor_bot.workspace.paths import resolve_paths


@dataclass(slots=True)
class ColdStartSmokeResult:
    """Result of provisioning a fresh runtime and running preflight."""

    ductor_home: Path
    config_path: Path
    workspace_path: Path
    preflight: PreflightReport

    @property
    def ok(self) -> bool:
        return (
            self.config_path.is_file()
            and self.workspace_path.is_dir()
            and not self.preflight.has_errors
        )


@contextmanager
def _patched_env(values: dict[str, str]) -> Iterator[None]:
    original = {key: os.environ.get(key) for key in values}
    try:
        for key, value in values.items():
            os.environ[key] = value
        yield
    finally:
        for key, previous in original.items():
            if previous is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = previous


def run_cold_start_smoke(
    ductor_home: str | Path,
    *,
    framework_root: str | Path,
) -> ColdStartSmokeResult:
    """Provision a fresh runtime in ``ductor_home`` and run preflight on it."""
    home = Path(ductor_home).expanduser().resolve()
    framework = Path(framework_root).expanduser().resolve()

    with _patched_env(
        {
            "DUCTOR_HOME": str(home),
            "DUCTOR_FRAMEWORK_ROOT": str(framework),
        }
    ):
        paths = resolve_paths(ductor_home=home, framework_root=framework)
        config_path = paths.config_path
        if not config_path.exists():
            config_path.parent.mkdir(parents=True, exist_ok=True)
            example = paths.config_example_path
            if example.is_file():
                user_data = json.loads(example.read_text(encoding="utf-8"))
            else:
                user_data = AgentConfig().model_dump(mode="json")
        else:
            user_data = json.loads(config_path.read_text(encoding="utf-8"))

        defaults = AgentConfig().model_dump(mode="json")
        defaults["gemini_api_key"] = DEFAULT_EMPTY_GEMINI_API_KEY
        defaults.pop("api", None)
        merged, _changed = deep_merge_config(user_data, defaults)
        if merged.get("gemini_api_key") is None:
            merged["gemini_api_key"] = DEFAULT_EMPTY_GEMINI_API_KEY
        atomic_json_save(config_path, merged)
        init_workspace(paths)

    report = run_runtime_preflight(home)
    return ColdStartSmokeResult(
        ductor_home=home,
        config_path=home / "config" / "config.json",
        workspace_path=home / "workspace",
        preflight=report,
    )
