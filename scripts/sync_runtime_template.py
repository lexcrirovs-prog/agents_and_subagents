#!/usr/bin/env python3
"""Initialize or refresh the public runtime template from the vendored framework."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path


_ENV_EXAMPLE = """# Copy this file to .env and fill the values you actually use.
# The runtime scripts load these values automatically when they are not already
# present in the shell environment.

DUCTOR_TELEGRAM_TOKEN=123456:replace-me

# Optional external providers:
# PPLX_API_KEY=replace-me
# DEEPSEEK_API_KEY=replace-me

# Optional enterprise sub-agent bot tokens:
# DUCTOR_AGENT_MARKETING_TELEGRAM_TOKEN=123456:replace-me
# DUCTOR_AGENT_LEGAL_TELEGRAM_TOKEN=123456:replace-me
# DUCTOR_AGENT_TECHNICAL_DIRECTOR_TELEGRAM_TOKEN=123456:replace-me
# DUCTOR_AGENT_PRODUCTION_TELEGRAM_TOKEN=123456:replace-me
# DUCTOR_AGENT_SALES_LEAD_TELEGRAM_TOKEN=123456:replace-me

# Optional source connectors and local paths:
# TELEGRAM_EXPORT_DIR=/path/to/telegram/export
# MAX_EXPORT_DIR=/path/to/max/export
# YOUTUBE_EXPORT_DIR=/path/to/youtube/transcripts
# SITE_EXPORT_DIR=/path/to/site/export
# NOTEBOOKLM_EXPORT_DIR=/path/to/notebooklm/export
# BEELINE_CALLS_EXPORT_DIR=/path/to/beeline/calls
# TRANSKRIB_PROG_DIR=/path/to/transkrib_prog
"""


_README = """# Runtime Template

This is the repo-local Ductor home template for `agents_and_subagents`.
It models an enterprise team: the main agent is the director, and sub-agents
act as departments.

## What is included in this baseline

- generic config and `.env` examples
- repo-local bootstrap / doctor / ready-check flow
- bounded tool surface: `task_tools`, `cron_tools`, `webhook_tools`, `agent_tools`
- enterprise skill pack copied from `skills-generic/`
- bundled shared/team layer for roster, handoff, reporting, and memory discipline
- context-hygiene scaffolding in `memory_system/context/`
- seeded `project-vault/` for the director and department structure
- a clean reusable sub-agent seed under `agents/_template/`

## Recommended install

1. Run `python3 ../scripts/subscriber_install.py`
2. Choose provider only if both Codex and Claude are already authenticated
3. Paste the Telegram bot token
4. Send the one-time `/pair CODE` message to the bot from the owner account
5. Let the installer write config, run strict preflight, and auto-start the runtime
6. Copy `agents.example.json` to `agents.json` after filling sub-agent bot tokens
   and allowed user ids
7. Start or restart the runtime so the director can delegate to departments

The installer bootstraps `.venv`, refreshes this template, writes `.env` and
`config/config.json`, binds the real Telegram owner id, and can leave the bot
running immediately after install.

## Maintenance commands

- `../scripts/bootstrap.sh` - refresh template and framework dependencies only
- `../scripts/doctor.sh` - re-run tooling/auth/runtime health checks
- `../scripts/run-main.sh` - start in the foreground when you intentionally use
  `subscriber_install.py --no-start` or want a manual foreground run

## Optional multi-agent scaffold

1. Edit `../agent-templates/team.example.json` if department roles change
2. Run `../scripts/render_agent_templates.py`
3. Copy `agents.example.json` to `agents.json`
4. Fill the matching agent token env vars in `.env`
5. Fill `allowed_user_ids` for the rendered agents before final doctor/start checks
6. After install, create extra departments with `workspace/tools/agent_tools/create_agent.py`

## Rules

- Keep this template generic and self-contained
- Do not add symlinks to external skill stores or sibling/private repos
- Copy this template for client installs; do not point it at any private runtime
"""


_HOME_GUIDE = """# Ductor Home

This is the repo-local Ductor home for the `agents_and_subagents` enterprise
team template.

## Cold Start (No Context)

Read in this order:

1. `workspace/AGENTS.md`
2. `workspace/tools/AGENTS.md`
3. `workspace/memory_system/MAINMEMORY.md`
4. `workspace/memory_system/context/` for live handoff state when present
5. `config/AGENTS.md` when settings changes are requested

## Top-Level Layout

- `workspace/` - main working area (tools, memory, cron tasks, skills, files)
- `config/config.json` - runtime configuration
- `logs/` - runtime logs
- `shared/` - bundled generic team docs and install-local shared knowledge
- `workspace/project-vault/` - install-local project/architecture vault seed

## Baseline Shape

- This baseline ships as a director runtime plus department sub-agent tooling.
- The shared/team layer defines the enterprise roster, handoff rules, reporting,
  and memory discipline inside this install.
- External source connectors are configured through env vars, exports, or local
  files; do not invent source facts before they are connected.
- Skills are bounded by `workspace/memory_system/profile/SkillRoster.md` and
  real local directories in `workspace/skills/`.

## Operating Rules

- Use tool scripts in `workspace/tools/` for task, cron, and webhook lifecycle
  changes.
- Keep the runtime self-contained: no symlinks to private repos, sibling
  folders, or global skill stores.
- Save user-facing generated files in `workspace/output_to_user/`.
- Update only requested keys in `config/config.json`.
"""


_WORKSPACE_GUIDE = """# Ductor Workspace Prompt

You are the director agent in the `agents_and_subagents` enterprise runtime.

## Startup (No Context)

1. Read this file completely.
2. Read `tools/AGENTS.md`, then the relevant tool subfolder `AGENTS.md`.
3. Read `memory_system/MAINMEMORY.md` and `memory_system/00-HOME.md` before
   long or stateful work.
4. Read `memory_system/context/SESSION_STATE.md`, `OPEN_LOOPS.md`, and
   `RECENT_DECISIONS.md` before long-running, stateful, or reset-sensitive work
   when they exist.
5. Read `project-vault/00-HOME.md` when the task concerns system architecture,
   install flow, team structure, or project management.
6. Read `../config/AGENTS.md` before changing runtime settings.

## Core Behavior

- Accept tasks from the user as the director.
- Route department work to the matching sub-agent.
- Require departments to solve cross-lane questions between themselves first.
- Integrate delegated results into one clear answer for the user.
- Ask only questions that unblock real progress.

## Memory Rules (Silent)

- Keep memory local to this client/runtime.
- Do not import or mirror notes from any other installation.
- Use `shared/` for install-local team/user facts that matter to more than one
  agent.
- Keep context-hygiene files in `memory_system/context/` short, factual, and
  current before considering substantial work complete.

## Tool Routing

Use `tools/AGENTS.md` as the index, then open the matching subfolder docs:

- `tools/agent_tools/AGENTS.md`
- `tools/task_tools/AGENTS.md`
- `tools/cron_tools/AGENTS.md`
- `tools/webhook_tools/AGENTS.md`

This baseline intentionally keeps `media_tools` and `user_tools` out of the
first public wave. `agent_tools` is included in a public-safe Telegram-first
form.

## Department Routing

- marketing messages and style learning -> `marketing`
- contracts and legal risk -> `legal`
- boiler engineering and normative knowledge -> `technical-director`
- production state and bottlenecks -> `production`
- sales calls and script quality -> `sales-lead`

## Skills

Skills live in `skills/`. Keep them bounded by:

- real local skill directories in `skills/`
- `memory_system/profile/SkillRoster.md` as the allow-list

## Safety Boundaries

- Ask before destructive actions.
- Ask before publishing or sending data to external systems.
- Prefer reversible operations.
"""


_TOOLS_GUIDE = """# Tools Directory

This is the navigation index for the public baseline tools.

## Global Rules

- Prefer these tool scripts over manual JSON/file surgery.
- Run with `python3`.
- Open the matching subfolder `AGENTS.md` before non-trivial changes.

## Routing

- sub-agent management and delegation -> `agent_tools/AGENTS.md`
- recurring tasks / schedules -> `cron_tools/AGENTS.md`
- incoming HTTP triggers -> `webhook_tools/AGENTS.md`
- background tasks -> `task_tools/AGENTS.md`

Not bundled in this baseline: `media_tools`, `user_tools`.

## External API Secrets

External API keys are loaded from `${DUCTOR_HOME:-$HOME/.ductor}/.env` and
injected into CLI subprocesses when present.

## Bot Restart

To restart the bot after config/runtime changes:

```bash
touch "${DUCTOR_HOME:-$HOME/.ductor}/restart-requested"
```

## Output and Memory

- Save user deliverables in `../output_to_user/`.
- Keep durable user/runtime facts in `../memory_system/`.
"""


_SKILLS_GUIDE = """# Skills Directory

This public template keeps skills self-contained and bounded.

## Rules

- Real local directories in this folder are the canonical installed skills.
- `memory_system/profile/SkillRoster.md` is the allow-list for the runtime
  skill surface.
- Do not add symlinks to `~/.claude`, `~/.codex`, `~/.gemini`, or sibling repos.
- If you add a vetted skill, copy it in as a real directory and update the
  local `SkillRoster.md`.

## Structure

Each skill lives in its own subdirectory:

```text
skills/my-skill/SKILL.md
```

Optional helpers can live in `scripts/`, `references/`, and other nested files.
"""


_AGENT_TOOLS_GUIDE = """# Agent Tools

Public-safe tools for inter-agent communication and local sub-agent registry
management.

## Available Tools

- `ask_agent.py` - sync request to another agent
- `ask_agent_async.py` - async handoff to another agent
- `create_agent.py` - create a Telegram sub-agent from the local clean template
- `remove_agent.py` - remove a sub-agent from `agents.json` while preserving its home
- `list_agents.py` - show configured sub-agents and their key settings

## Rules

- `create_agent.py`, `remove_agent.py`, and `list_agents.py` are main-runtime tools.
- Bot tokens must stay env-backed (`env:...`), not hardcoded into `agents.json`.
- The clean reusable seed lives under `agents/_template/`.
- The reply from `ask_agent.py` or `ask_agent_async.py` returns to the calling
  agent, not directly to the target bot's own chat.
"""


_MEMORY_GUIDE = """# Memory System

`memory_system/` is the local long-term memory for this install.
`MAINMEMORY.md` is the compact operating memory across sessions.

## Silence Is Mandatory

Never tell the user you are reading or writing memory.

## Read First

1. `MAINMEMORY.md`
2. `00-HOME.md`
3. The relevant note in `profile/`, `people/`, `projects/`, `decisions/`, or `daily/`
4. `context/SESSION_STATE.md`, `context/OPEN_LOOPS.md`, and
   `context/RECENT_DECISIONS.md` for long-running or restart-sensitive work
5. `../project-vault/` when system architecture, install flow, or roadmap state
   matters

## What Belongs Here

- durable user and project facts for this install
- important decisions and rationale
- recurring workflow preferences
- daily summaries and project state
- compact session handoff state in `context/`

## What Does Not Belong Here

- secrets, tokens, API keys
- transient debugging noise
- copied notes from another runtime
- one-off throwaway requests

## Daily Note Rule

Use one note per calendar day in the configured user timezone, and move stable
facts out of daily logs into typed notes.

## Context Hygiene Rule

Keep `context/SESSION_STATE.md`, `OPEN_LOOPS.md`, and `RECENT_DECISIONS.md`
short and factual. They exist to survive resets, restarts, or long-running
install/operator work without dragging raw chat history around.
"""


_PEOPLE_README = """# People

Store durable notes about collaborators, customers, and recurring contacts here.
"""


_TELEGRAM_FILES_GUIDE = """# Telegram Files

Incoming Telegram files are stored here, grouped by date.

This baseline treats the directory as raw inbound storage. A richer media
processing layer can be added later, but it is not bundled in the first public
wave.

## Rules

- Do not manually edit generated indexes or hidden sidecars if they appear.
- Do not move or delete files unless the user asked for it.
- Keep this directory as runtime state, not as product source content.
"""


_SHARED_HOME = """---
type: shared-home
updated: 2026-04-20
---

# Shared Core

This folder is optional. Use it only for generic docs that belong to this
install and matter to more than one agent or process.

## Rule

- Keep it local to this runtime.
- Do not copy private team vaults, journals, or user archives into it.
- If a fact matters only to one assistant, keep it in that assistant's local
  memory instead.
- Bundled generic team docs live in `shared/team/` and may be adapted for this
  install without importing private material from another runtime.
"""


_CONTEXT_POLICY = """# Context Hygiene

This folder stores compact handoff state between long-lived sessions.

## Rules

- Keep entries brief and factual.
- Do not paste raw chat transcript here.
- Update after milestones, before `/new`, and after major tool-heavy turns.
- Record only what the next session needs to continue cleanly.
"""


_SESSION_STATE = """# Session State

## Current Focus

- No active focus recorded yet.

## Key Files

- None recorded yet.

## Resume Notes

- Refresh this file after important milestones or before resetting context.
"""


_OPEN_LOOPS = """# Open Loops

- No open loops recorded yet.
"""


_RECENT_DECISIONS = """# Recent Decisions

- No install-local decisions recorded yet.
"""


_SUBAGENT_HOME_GUIDE = """# Ductor Home

This is the isolated Ductor home for sub-agent `{name}` in the public
`agents_and_subagents` enterprise template.

## Role

- Public name: `{public_name}`
- Lane: {role_title}
- Mission: {role_summary}

## Cold Start (No Context)

Read in this order:

1. `workspace/AGENTS.md`
2. `workspace/tools/AGENTS.md`
3. `workspace/memory_system/MAINMEMORY.md`
4. `config/AGENTS.md` when settings changes are requested

## Top-Level Layout

- `workspace/` - isolated agent working area
- `config/config.json` - local runtime config scaffold
- `logs/` - runtime logs for this home when present
- `shared/` - install-local shared/team canon for this agent group

## Operating Rules

- Stay inside your lane and return concise, checkable results.
- Ask peer departments directly when their lane is needed.
- Return resolved answers to the director instead of forwarding raw questions.
- Keep this home self-contained and client-safe.
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
- Ask peer departments directly for cross-lane facts.
- Integrate peer answers before reporting to the director.
- Escalate only unresolved decisions, missing access, or material conflicts.

## Startup (No Context)

1. Read this file completely.
2. Read `tools/AGENTS.md`, then the relevant tool subfolder `AGENTS.md`.
3. Read `memory_system/MAINMEMORY.md` and `memory_system/00-HOME.md` before
   long or stateful work.
4. Read `memory_system/context/SESSION_STATE.md`, `OPEN_LOOPS.md`, and
   `RECENT_DECISIONS.md` before long-running, stateful, or reset-sensitive work
   when they exist.
5. Read `shared/team/AgentRoster.md` when lane ownership, handoff, or memory
   discipline matters.
6. Read `../config/AGENTS.md` before changing runtime settings.

## Tool Routing

Use `tools/AGENTS.md` as the index, then open the matching subfolder docs:

- `tools/agent_tools/AGENTS.md`
- `tools/task_tools/AGENTS.md`
- `tools/cron_tools/AGENTS.md`
- `tools/webhook_tools/AGENTS.md`

## Skills

Skills live in `skills/` and are bounded by the local `SkillRoster.md`.

## Memory And Team Rules

- Keep private working memory in `workspace/memory_system/`.
- Use `shared/team/` for install-local roster, handoff, reporting, and memory
  rules that matter across agents.
- Update context-hygiene files before treating substantial work as complete.
- Never invent source facts from Telegram, MAX, YouTube, NotebookLM, Beeline, or
  production files; name the missing connector or file.

## Safety Boundaries

- Ask before destructive actions.
- Ask before publishing or sending data to external systems.
- Prefer reversible operations.
"""


_SUBAGENT_MAINMEMORY = """# MAINMEMORY

## Identity

- You are `{public_name}`, an install-safe department agent.
- Your runtime name is `{name}`.
- Your lane is: {role_title}
- Your mission is: {role_summary}

## Operating Rules

- Stay inside your lane unless the operator explicitly widens scope.
- Return concise, checkable results.
- Ask peer departments for off-lane input instead of improvising authority.
- Report one resolved answer upward after peer consultation.
- Escalate only when access, approval, or department conflict remains.
- Keep this memory local to this install.
"""


_RULE_DOCS = ("AGENTS.md", "CLAUDE.md", "GEMINI.md")
_ALLOWED_TOOLS = {
    *_RULE_DOCS,
    "_internal_api.py",
    "_runtime_paths.py",
    "_tool_shared.py",
    "agent_tools",
    "task_tools",
    "cron_tools",
    "webhook_tools",
}
_PUBLIC_AGENT_TOOL_NAMES = {
    *_RULE_DOCS,
    "_shared.py",
    "ask_agent.py",
    "ask_agent_async.py",
    "create_agent.py",
    "list_agents.py",
    "remove_agent.py",
}
_AGENT_PRIMARY_SKILLS = {
    "main": ["enterprise-collaboration", "writing-plans", "systematic-debugging"],
    "marketing": ["enterprise-collaboration", "marketing-content-ops", "writing-plans"],
    "legal": ["enterprise-collaboration", "legal-contract-review", "writing-plans"],
    "technical-director": [
        "enterprise-collaboration",
        "technical-director-knowledge",
        "systematic-debugging",
    ],
    "production": ["enterprise-collaboration", "production-bottleneck-analysis", "writing-plans"],
    "sales-lead": ["enterprise-collaboration", "sales-call-quality", "writing-plans"],
}


def _root_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def _write_triplet(directory: Path, content: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name in _RULE_DOCS:
        (directory / name).write_text(content, encoding="utf-8")


def _remove_path(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if path.is_symlink() or path.is_file():
        path.unlink()
        return
    shutil.rmtree(path, ignore_errors=True)


def _write_if_missing(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return
    path.write_text(content, encoding="utf-8")


def _prune_directory(directory: Path, allowed_names: set[str]) -> None:
    if not directory.is_dir():
        return
    for entry in directory.iterdir():
        if entry.name not in allowed_names:
            _remove_path(entry)


def _sync_generic_team_docs(root: Path, runtime_home: Path) -> None:
    source_root = root / "shared-generic" / "team"
    target_root = runtime_home / "shared" / "team"
    target_root.mkdir(parents=True, exist_ok=True)

    allowed = {path.name for path in source_root.glob("*.md")}
    _prune_directory(target_root, allowed)

    for source in sorted(source_root.glob("*.md")):
        if not source.is_file():
            continue
        shutil.copy2(source, target_root / source.name)


def _seed_if_missing_tree(source_root: Path, target_root: Path) -> None:
    for source in sorted(source_root.rglob("*")):
        rel = source.relative_to(source_root)
        target = target_root / rel
        if source.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        _write_if_missing(target, source.read_text(encoding="utf-8"))


def _seed_generic_project_vault(root: Path, runtime_home: Path) -> None:
    source_root = root / "project-vault-generic"
    if not source_root.is_dir():
        return
    target_root = runtime_home / "workspace" / "project-vault"
    _seed_if_missing_tree(source_root, target_root)


def _ensure_context_hygiene(runtime_home: Path) -> None:
    context_dir = runtime_home / "workspace" / "memory_system" / "context"
    _write_if_missing(context_dir / "POLICY.md", _CONTEXT_POLICY)
    _write_if_missing(context_dir / "SESSION_STATE.md", _SESSION_STATE)
    _write_if_missing(context_dir / "OPEN_LOOPS.md", _OPEN_LOOPS)
    _write_if_missing(context_dir / "RECENT_DECISIONS.md", _RECENT_DECISIONS)


def _initialize_home(root: Path, runtime_home: Path) -> None:
    framework_root = root / "ductor"
    if str(framework_root) not in sys.path:
        sys.path.insert(0, str(framework_root))

    from ductor_bot.workspace.init import init_workspace
    from ductor_bot.workspace.paths import resolve_paths

    init_workspace(resolve_paths(ductor_home=runtime_home))


def _load_framework_example(framework_root: Path) -> dict[str, object]:
    config_path = framework_root / "config.example.json"
    return json.loads(config_path.read_text(encoding="utf-8"))


def _build_public_config(raw: dict[str, object]) -> dict[str, object]:
    data = dict(raw)
    data["_comment"] = "Public install config. Edit this file in place for the current runtime."
    data["provider"] = "codex"
    data["model"] = "gpt-5.4"
    data["reasoning_effort"] = "high"
    data["telegram_token"] = "env:DUCTOR_TELEGRAM_TOKEN"
    data["allowed_user_ids"] = []
    data["allowed_group_ids"] = []
    data["group_mention_only"] = False
    data["transport"] = "telegram"
    data["transports"] = ["telegram"]
    data.pop("ductor_home", None)

    docker = data.get("docker")
    if isinstance(docker, dict):
        docker["enabled"] = False
        docker["mounts"] = []
        docker["extras"] = []

    heartbeat = data.get("heartbeat")
    if isinstance(heartbeat, dict):
        heartbeat["enabled"] = False
        heartbeat["group_targets"] = []

    webhooks = data.get("webhooks")
    if isinstance(webhooks, dict):
        webhooks["enabled"] = False
        webhooks["token"] = "env:DUCTOR_WEBHOOK_TOKEN"

    api = data.get("api")
    if isinstance(api, dict):
        api["enabled"] = False
        api["token"] = "env:DUCTOR_API_TOKEN"

    return data


def _bundled_skill_names(source_root: Path) -> list[str]:
    if not source_root.is_dir():
        return []
    return sorted(path.name for path in source_root.iterdir() if path.is_dir())


def _render_skill_roster(skill_names: list[str], *, agent_name: str = "main") -> str:
    primary = [name for name in _AGENT_PRIMARY_SKILLS.get(agent_name, []) if name in skill_names]
    remaining = [name for name in skill_names if name not in set(primary)]
    lines = ["# Skill Roster", "", f"## Default-first skills for `{agent_name}`", ""]
    lines.extend(f"- `{name}`" for name in primary or skill_names)
    if primary and remaining:
        lines.extend(["", "## Available supporting skills", ""])
        lines.extend(f"- `{name}`" for name in remaining)
    return "\n".join(lines) + "\n"


def _render_subagent_home_guide(
    *,
    name: str,
    public_name: str,
    role_title: str,
    role_summary: str,
) -> str:
    return _SUBAGENT_HOME_GUIDE.format(
        name=name,
        public_name=public_name or name,
        role_title=role_title or "generic department",
        role_summary=role_summary or "Own one bounded lane and report concise results.",
    )


def _render_subagent_workspace_guide(
    *,
    name: str,
    public_name: str,
    role_title: str,
    role_summary: str,
) -> str:
    return _SUBAGENT_WORKSPACE_GUIDE.format(
        name=name,
        public_name=public_name or name,
        role_title=role_title or "generic department",
        role_summary=role_summary or "Own one bounded lane and report concise results.",
    )


def _render_subagent_mainmemory(
    *,
    name: str,
    public_name: str,
    role_title: str,
    role_summary: str,
) -> str:
    return _SUBAGENT_MAINMEMORY.format(
        name=name,
        public_name=public_name or name,
        role_title=role_title or "generic department",
        role_summary=role_summary or "Own one bounded lane and report concise results.",
    )


def _sync_bundled_skills(root: Path, runtime_home: Path, *, agent_name: str = "main") -> None:
    source_root = root / "skills-generic"
    target_root = runtime_home / "workspace" / "skills"
    target_root.mkdir(parents=True, exist_ok=True)

    skill_names = _bundled_skill_names(source_root)
    allowed_names = set(_RULE_DOCS) | set(skill_names)
    _prune_directory(target_root, allowed_names)

    for skill_name in skill_names:
        source = source_root / skill_name
        target = target_root / skill_name
        _remove_path(target)
        shutil.copytree(source, target)

    _write_triplet(target_root, _SKILLS_GUIDE)

    roster_path = runtime_home / "workspace" / "memory_system" / "profile" / "SkillRoster.md"
    roster_path.parent.mkdir(parents=True, exist_ok=True)
    roster_path.write_text(_render_skill_roster(skill_names, agent_name=agent_name), encoding="utf-8")


def _sync_public_agent_tools(root: Path, runtime_home: Path) -> None:
    source_root = (
        root / "ductor" / "ductor_bot" / "_home_defaults" / "workspace" / "tools" / "agent_tools"
    )
    target_root = runtime_home / "workspace" / "tools" / "agent_tools"
    target_root.mkdir(parents=True, exist_ok=True)
    _prune_directory(target_root, _PUBLIC_AGENT_TOOL_NAMES)

    for filename in sorted(_PUBLIC_AGENT_TOOL_NAMES - set(_RULE_DOCS)):
        source = source_root / filename
        if not source.is_file():
            msg = f"Missing public agent tool source: {source}"
            raise FileNotFoundError(msg)
        target = target_root / filename
        _remove_path(target)
        shutil.copy2(source, target)

    _write_triplet(target_root, _AGENT_TOOLS_GUIDE)


def _write_public_config_files(runtime_home: Path, config: dict[str, object]) -> None:
    config_dir = runtime_home / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(config, ensure_ascii=False, indent=2) + "\n"
    (config_dir / "config.example.json").write_text(rendered, encoding="utf-8")
    (config_dir / "config.json").write_text(rendered, encoding="utf-8")


def _sync_common_surface(
    root: Path,
    runtime_home: Path,
    *,
    home_guide: str,
    workspace_guide: str,
    agent_name: str = "main",
) -> None:
    tools_dir = runtime_home / "workspace" / "tools"
    _prune_directory(tools_dir, _ALLOWED_TOOLS)
    shared_dir = runtime_home / "shared"
    _prune_directory(shared_dir, {"00-HOME.md"})
    _write_triplet(runtime_home, home_guide)
    _write_triplet(runtime_home / "workspace", workspace_guide)
    _write_triplet(tools_dir, _TOOLS_GUIDE)
    _write_triplet(runtime_home / "workspace" / "memory_system", _MEMORY_GUIDE)
    people_readme = runtime_home / "workspace" / "memory_system" / "people" / "README.md"
    people_readme.parent.mkdir(parents=True, exist_ok=True)
    people_readme.write_text(_PEOPLE_README, encoding="utf-8")
    _write_triplet(runtime_home / "workspace" / "telegram_files", _TELEGRAM_FILES_GUIDE)
    (shared_dir / "00-HOME.md").write_text(_SHARED_HOME, encoding="utf-8")
    _sync_generic_team_docs(root, runtime_home)
    _ensure_context_hygiene(runtime_home)
    _seed_generic_project_vault(root, runtime_home)
    _sync_public_agent_tools(root, runtime_home)
    _sync_bundled_skills(root, runtime_home, agent_name=agent_name)


def _sanitize_runtime_state(runtime_home: Path) -> None:
    """Remove host-derived runtime artifacts that must never ship in the template."""
    codex_dirs = [runtime_home / ".codex"]
    agents_dir = runtime_home / "agents"
    if agents_dir.is_dir():
        codex_dirs.extend(sorted(agent_dir / ".codex" for agent_dir in agents_dir.iterdir() if agent_dir.is_dir()))
    for codex_dir in codex_dirs:
        _remove_path(codex_dir)


def _sanitize_runtime_template(root: Path, runtime_home: Path) -> None:
    _sync_common_surface(root, runtime_home, home_guide=_HOME_GUIDE, workspace_guide=_WORKSPACE_GUIDE)
    _sanitize_runtime_state(runtime_home)


def sync_public_subagent_home(
    root: Path,
    agent_home: Path,
    *,
    name: str,
    public_name: str = "",
    role_title: str = "",
    role_summary: str = "",
    join_notification: str | None = None,
) -> None:
    _initialize_home(root, agent_home)
    _sync_common_surface(
        root,
        agent_home,
        home_guide=_render_subagent_home_guide(
            name=name,
            public_name=public_name,
            role_title=role_title,
            role_summary=role_summary,
        ),
        workspace_guide=_render_subagent_workspace_guide(
            name=name,
            public_name=public_name,
            role_title=role_title,
            role_summary=role_summary,
        ),
        agent_name=name,
    )
    config = _build_public_config(_load_framework_example(root / "ductor"))
    _write_public_config_files(agent_home, config)
    mainmemory_path = agent_home / "workspace" / "memory_system" / "MAINMEMORY.md"
    mainmemory_path.write_text(
        _render_subagent_mainmemory(
            name=name,
            public_name=public_name,
            role_title=role_title,
            role_summary=role_summary,
        ),
        encoding="utf-8",
    )
    if join_notification and join_notification.strip():
        (agent_home / "workspace" / "JOIN_NOTIFICATION.md").write_text(
            join_notification.strip() + "\n",
            encoding="utf-8",
        )
    _sanitize_runtime_state(agent_home)


def main() -> int:
    root = _root_dir()
    framework_root = root / "ductor"
    runtime_home = root / "runtime-template"

    _initialize_home(root, runtime_home)

    config = _build_public_config(_load_framework_example(framework_root))
    _write_public_config_files(runtime_home, config)

    (runtime_home / ".env.example").write_text(_ENV_EXAMPLE, encoding="utf-8")
    (runtime_home / "README.md").write_text(_README, encoding="utf-8")
    _sanitize_runtime_template(root, runtime_home)
    sync_public_subagent_home(
        root,
        runtime_home / "agents" / "_template",
        name="template",
        public_name="Template",
        role_title="generic department",
        role_summary="Own one bounded lane and report concise, checkable results.",
    )

    print(runtime_home)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
