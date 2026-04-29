#!/usr/bin/env python3
"""Render public-safe sub-agent homes and agents.example.json from a manifest."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from sync_runtime_template import sync_public_subagent_home


_NAME_RE = re.compile(r"^[a-z][a-z0-9_-]{1,31}$")


def _root_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def _manifest_path(root: Path) -> Path:
    return root / "agent-templates" / "team.example.json"


def _load_manifest(path: Path) -> list[dict[str, object]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    agents = raw.get("agents")
    if not isinstance(agents, list):
        msg = f"Invalid manifest: expected 'agents' list in {path}"
        raise ValueError(msg)
    return agents


def _require_string(agent: dict[str, object], key: str, *, default: str = "") -> str:
    value = agent.get(key, default)
    if not isinstance(value, str):
        msg = f"Invalid '{key}' for agent entry: expected string"
        raise ValueError(msg)
    return value.strip()


def _normalize_name(name: str) -> str:
    if not _NAME_RE.fullmatch(name):
        msg = f"Invalid agent name '{name}'. Use lowercase letters, digits, '-' or '_'."
        raise ValueError(msg)
    return name


def _render_agents_example(agents: list[dict[str, object]]) -> list[dict[str, object]]:
    rendered: list[dict[str, object]] = []
    for agent in agents:
        name = _normalize_name(_require_string(agent, "name"))
        public_name = _require_string(agent, "public_name", default=name)
        token_env = _require_string(agent, "telegram_token_env")
        provider = _require_string(agent, "provider", default="codex") or "codex"
        model = _require_string(agent, "model", default="gpt-5.4") or "gpt-5.4"
        reasoning = _require_string(agent, "reasoning_effort", default="high") or "high"
        rendered.append(
            {
                "name": name,
                "public_name": public_name,
                "telegram_token": f"env:{token_env}",
                "allowed_user_ids": [],
                "allowed_group_ids": [],
                "provider": provider,
                "model": model,
                "reasoning_effort": reasoning,
            }
        )
    return rendered


def main() -> int:
    root = _root_dir()
    runtime_home = root / "runtime-template"
    manifest_path = _manifest_path(root)
    agents = _load_manifest(manifest_path)

    rendered_agents = _render_agents_example(agents)
    agents_example_path = runtime_home / "agents.example.json"
    agents_example_path.write_text(
        json.dumps(rendered_agents, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    agents_root = runtime_home / "agents"
    keep = {entry["name"] for entry in rendered_agents} | {"_template"}
    if agents_root.is_dir():
        for child in agents_root.iterdir():
            if child.name not in keep:
                if child.is_symlink() or child.is_file():
                    child.unlink()
                else:
                    import shutil

                    shutil.rmtree(child, ignore_errors=True)

    for agent in agents:
        name = _normalize_name(_require_string(agent, "name"))
        join_notification = _require_string(agent, "join_notification", default="")
        if not join_notification:
            join_notification = _require_string(agent, "description", default="")
        sync_public_subagent_home(
            root,
            agents_root / name,
            name=name,
            public_name=_require_string(agent, "public_name", default=name),
            role_title=_require_string(agent, "role_title", default="generic specialist"),
            role_summary=_require_string(
                agent,
                "role_summary",
                default="Own one bounded lane and report concise results.",
            ),
            join_notification=join_notification or None,
        )

    print(agents_example_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
