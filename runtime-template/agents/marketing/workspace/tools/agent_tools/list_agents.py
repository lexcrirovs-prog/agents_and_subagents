#!/usr/bin/env python3
"""List all registered sub-agents and their configuration.

Usage:
    python3 list_agents.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True

TOOLS_DIR = str(Path(__file__).resolve().parents[1])
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

from _runtime_paths import resolve_main_ductor_home


def _agents_path() -> Path:
    """Resolve agents.json path (always in main agent home).

    Works both inside the bot process and from an arbitrary runtime workspace.
    """
    return resolve_main_ductor_home() / "agents.json"


def _format_token(value: object) -> str:
    token = str(value or "").strip()
    if not token:
        return "(missing)"
    if token.startswith("env:"):
        return token
    return "[inline secret]"


def main() -> None:
    path = _agents_path()
    if not path.is_file():
        print("No agents.json found. No sub-agents configured.")
        return

    try:
        agents = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        print("Error: Failed to read agents.json", file=sys.stderr)
        sys.exit(1)

    if not agents:
        print("No sub-agents configured.")
        return

    print(f"Registered sub-agents ({len(agents)}):\n")
    for agent in agents:
        name = agent.get("name", "?")
        token = agent.get("telegram_token", "?")
        users = agent.get("allowed_user_ids", [])
        provider = agent.get("provider", "(inherited)")
        model = agent.get("model", "(inherited)")

        # Check if workspace exists
        home = Path(_agents_path().parent / "agents" / name)
        workspace_status = "exists" if home.is_dir() else "not created"

        print(f"  {name}")
        print(f"    Token:     {_format_token(token)}")
        print(f"    Users:     {users}")
        print(f"    Provider:  {provider}")
        print(f"    Model:     {model}")
        print(f"    Workspace: {workspace_status}")
        print()


if __name__ == "__main__":
    main()
