#!/usr/bin/env python3
"""Shared helpers for the public-safe agent tools."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from _runtime_paths import resolve_ductor_home, resolve_main_ductor_home


_NAME_RE = re.compile(r"^[a-z][a-z0-9_-]{1,31}$")
_ENV_VAR_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
_RULE_DOCS = ("AGENTS.md", "CLAUDE.md", "GEMINI.md")
_TEMPLATE_DIR_NAME = "_template"

_SUBAGENT_HOME_GUIDE = """# Ductor Home

This is the isolated Ductor home for sub-agent `{name}`.

## Role

- Public name: `{public_name}`
- Lane: {role_title}
- Mission: {role_summary}

## Operating Rules

- Stay inside your lane and return concise, checkable results.
- Keep this home self-contained and install-safe.
- Do not create symlinks to sibling or private repos.
"""

_SUBAGENT_WORKSPACE_GUIDE = """# Ductor Workspace Prompt

You are sub-agent `{name}`.

## Role

- Public name: `{public_name}`
- Lane: {role_title}
- Mission: {role_summary}

## Core Behavior

- Work inside your lane first.
- Return concise, actionable output.
- Escalate cross-lane or ambiguous work back to the main agent/operator.

## Startup (No Context)

1. Read this file completely.
2. Read `tools/AGENTS.md`, then the relevant tool subfolder `AGENTS.md`.
3. Read `memory_system/MAINMEMORY.md` and `memory_system/00-HOME.md` before
   long or stateful work.
4. Read `../config/AGENTS.md` before changing runtime settings.
"""

_SUBAGENT_MAINMEMORY = """# MAINMEMORY

## Identity

- You are `{public_name}`, an install-safe specialist agent.
- Your runtime name is `{name}`.
- Your lane is: {role_title}
- Your mission is: {role_summary}

## Operating Rules

- Stay inside your lane unless the operator explicitly widens scope.
- Return concise, checkable results.
- Escalate off-lane work instead of improvising authority you do not have.
- Keep this memory local to this install.
"""


def current_home() -> Path:
    return resolve_ductor_home().resolve()


def main_home() -> Path:
    return resolve_main_ductor_home().resolve()


def ensure_main_runtime() -> Path:
    current = current_home()
    main = main_home()
    if current != main:
        msg = "This tool can only be run from the main runtime home."
        raise RuntimeError(msg)
    return main


def template_home(home: Path | None = None) -> Path:
    return (home or main_home()) / "agents" / _TEMPLATE_DIR_NAME


def agents_path(home: Path | None = None) -> Path:
    return (home or main_home()) / "agents.json"


def load_agents(home: Path | None = None) -> list[dict[str, object]]:
    path = agents_path(home)
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        msg = f"Failed to read {path}: {exc}"
        raise RuntimeError(msg) from exc
    if not isinstance(raw, list):
        msg = f"Invalid agent registry at {path}: expected a JSON list."
        raise RuntimeError(msg)
    return raw


def save_agents(agents: list[dict[str, object]], home: Path | None = None) -> Path:
    path = agents_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(agents, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def normalize_name(raw: str) -> str:
    name = raw.strip().lower()
    if name == "main" or name == _TEMPLATE_DIR_NAME or not _NAME_RE.fullmatch(name):
        msg = f"Invalid agent name '{raw}'. Use lowercase letters, digits, '-' or '_'."
        raise ValueError(msg)
    return name


def validate_env_var_name(raw: str) -> str:
    name = raw.strip().upper()
    if not _ENV_VAR_RE.fullmatch(name):
        msg = f"Invalid environment variable name '{raw}'."
        raise ValueError(msg)
    return name


def parse_int_csv(raw: str, label: str, *, required: bool = False) -> list[int]:
    values = [part.strip() for part in raw.split(",") if part.strip()]
    if not values:
        if required:
            msg = f"{label} requires at least one integer value."
            raise ValueError(msg)
        return []
    parsed: list[int] = []
    for value in values:
        try:
            parsed.append(int(value))
        except ValueError as exc:
            msg = f"{label} values must be integers: '{value}' is invalid."
            raise ValueError(msg) from exc
    return parsed


def default_public_name(name: str) -> str:
    return name.replace("-", " ").replace("_", " ").title()


def write_triplet(directory: Path, content: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name in _RULE_DOCS:
        (directory / name).write_text(content, encoding="utf-8")


def render_subagent_home_guide(
    *,
    name: str,
    public_name: str,
    role_title: str,
    role_summary: str,
) -> str:
    return _SUBAGENT_HOME_GUIDE.format(
        name=name,
        public_name=public_name or name,
        role_title=role_title or "generic specialist",
        role_summary=role_summary or "Own one bounded lane and report concise results.",
    )


def render_subagent_workspace_guide(
    *,
    name: str,
    public_name: str,
    role_title: str,
    role_summary: str,
) -> str:
    return _SUBAGENT_WORKSPACE_GUIDE.format(
        name=name,
        public_name=public_name or name,
        role_title=role_title or "generic specialist",
        role_summary=role_summary or "Own one bounded lane and report concise results.",
    )


def render_subagent_mainmemory(
    *,
    name: str,
    public_name: str,
    role_title: str,
    role_summary: str,
) -> str:
    return _SUBAGENT_MAINMEMORY.format(
        name=name,
        public_name=public_name or name,
        role_title=role_title or "generic specialist",
        role_summary=role_summary or "Own one bounded lane and report concise results.",
    )


def provision_subagent_home(
    *,
    home: Path,
    name: str,
    public_name: str,
    role_title: str,
    role_summary: str,
    join_notification: str | None,
) -> Path:
    source = template_home(home)
    if not source.is_dir():
        msg = (
            f"Missing clean sub-agent template at {source}. "
            "Refresh the runtime template first."
        )
        raise RuntimeError(msg)

    target = home / "agents" / name
    shutil.copytree(source, target)
    write_triplet(
        target,
        render_subagent_home_guide(
            name=name,
            public_name=public_name,
            role_title=role_title,
            role_summary=role_summary,
        ),
    )
    write_triplet(
        target / "workspace",
        render_subagent_workspace_guide(
            name=name,
            public_name=public_name,
            role_title=role_title,
            role_summary=role_summary,
        ),
    )
    (target / "workspace" / "memory_system" / "MAINMEMORY.md").write_text(
        render_subagent_mainmemory(
            name=name,
            public_name=public_name,
            role_title=role_title,
            role_summary=role_summary,
        ),
        encoding="utf-8",
    )
    if join_notification and join_notification.strip():
        (target / "workspace" / "JOIN_NOTIFICATION.md").write_text(
            join_notification.strip() + "\n",
            encoding="utf-8",
        )
    return target


def update_local_agent_config(
    agent_home: Path,
    *,
    provider: str | None,
    model: str | None,
    reasoning_effort: str | None,
    token_env: str,
    allowed_user_ids: list[int],
    allowed_group_ids: list[int],
    group_mention_only: bool,
) -> None:
    for filename in ("config.json", "config.example.json"):
        path = agent_home / "config" / filename
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            msg = f"Failed to update {path}: {exc}"
            raise RuntimeError(msg) from exc
        if provider:
            data["provider"] = provider
        if model:
            data["model"] = model
        if reasoning_effort:
            data["reasoning_effort"] = reasoning_effort
        data["telegram_token"] = f"env:{token_env}"
        data["allowed_user_ids"] = allowed_user_ids
        data["allowed_group_ids"] = allowed_group_ids
        data["group_mention_only"] = group_mention_only
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
