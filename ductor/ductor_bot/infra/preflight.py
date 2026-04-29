"""Runtime preflight checks for deterministic launches and operator setup."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

_TOKEN_PATTERN = re.compile(r"^\d{6,}:[A-Za-z0-9_-]{10,}$")
_PLACEHOLDER_PREFIXES = ("YOUR_", "CHANGE_ME", "PASTE_")
_ENV_REF_PREFIX = "env:"


@dataclass(slots=True)
class PreflightIssue:
    """A single runtime preflight finding."""

    severity: Literal["error", "warning"]
    code: str
    message: str
    path: str | None = None


@dataclass(slots=True)
class PreflightReport:
    """Structured preflight report for one runtime home."""

    ductor_home: Path
    issues: list[PreflightIssue]

    @property
    def has_errors(self) -> bool:
        return any(issue.severity == "error" for issue in self.issues)

    @property
    def has_warnings(self) -> bool:
        return any(issue.severity == "warning" for issue in self.issues)

    @property
    def ok(self) -> bool:
        return not self.issues


def _issue(
    issues: list[PreflightIssue],
    severity: Literal["error", "warning"],
    code: str,
    message: str,
    *,
    path: str | None = None,
) -> None:
    issues.append(PreflightIssue(severity=severity, code=code, message=message, path=path))


def _load_json(path: Path, issues: list[PreflightIssue], *, required: bool) -> Any | None:
    if not path.exists():
        if required:
            _issue(
                issues,
                "error",
                "missing_file",
                f"Missing required file: {path.name}",
                path=str(path),
            )
        return None

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        _issue(
            issues,
            "error",
            "invalid_json",
            f"Invalid JSON in {path.name}: {exc}",
            path=str(path),
        )
        return None


def _active_transports(config: dict[str, Any]) -> list[str]:
    transports = config.get("transports")
    if isinstance(transports, list):
        values = [str(item).strip() for item in transports if str(item).strip()]
        if values:
            return values
    transport = str(config.get("transport", "")).strip()
    return [transport] if transport else ["telegram"]


def _is_placeholder(value: str) -> bool:
    return any(value.startswith(prefix) for prefix in _PLACEHOLDER_PREFIXES)


def _validate_token_value(
    token: str,
    issues: list[PreflightIssue],
    *,
    prefix: str,
    code_prefix: str,
    path: str,
) -> None:
    if not token or _is_placeholder(token):
        _issue(
            issues,
            "warning",
            f"{code_prefix}_telegram_token_missing",
            f"{prefix} Telegram token is missing or still a placeholder.",
            path=path,
        )
        return

    if token.startswith(_ENV_REF_PREFIX):
        env_name = token[len(_ENV_REF_PREFIX) :].strip()
        if not env_name:
            _issue(
                issues,
                "warning",
                f"{code_prefix}_telegram_token_missing",
                f"{prefix} Telegram token env reference is empty.",
                path=path,
            )
            return
        env_value = os.environ.get(env_name, "").strip()
        if env_value and not _TOKEN_PATTERN.match(env_value):
            _issue(
                issues,
                "warning",
                f"{code_prefix}_telegram_token_suspicious",
                f"{prefix} Telegram token env reference '{env_name}' is set but does not look valid.",
                path=path,
            )
        return

    if not _TOKEN_PATTERN.match(token):
        _issue(
            issues,
            "warning",
            f"{code_prefix}_telegram_token_suspicious",
            f"{prefix} Telegram token does not match the expected BotFather format.",
            path=path,
        )


def _validate_telegram_config(
    config: dict[str, Any],
    issues: list[PreflightIssue],
    *,
    prefix: str,
    code_prefix: str,
    path: str,
) -> None:
    token = str(config.get("telegram_token", "")).strip()
    users = config.get("allowed_user_ids", [])
    _validate_token_value(
        token,
        issues,
        prefix=prefix,
        code_prefix=code_prefix,
        path=path,
    )

    if not isinstance(users, list) or not any(isinstance(item, int) and item > 0 for item in users):
        _issue(
            issues,
            "warning",
            f"{code_prefix}_allowed_users_missing",
            f"{prefix} allowed_user_ids is empty or invalid.",
            path=path,
        )


def _validate_main_config(config: dict[str, Any], issues: list[PreflightIssue], path: Path) -> None:
    transports = _active_transports(config)
    if "telegram" in transports:
        _validate_telegram_config(
            config,
            issues,
            prefix="Main",
            code_prefix="main",
            path=str(path),
        )

    port = config.get("interagent_port")
    if port not in (None, ""):
        try:
            parsed = int(port)
        except (TypeError, ValueError):
            parsed = 0
        if not 0 < parsed < 65536:
            _issue(
                issues,
                "error",
                "invalid_interagent_port",
                "interagent_port must be between 1 and 65535.",
                path=str(path),
            )


def _validate_agents_registry(
    agents: Any,
    issues: list[PreflightIssue],
    *,
    path: Path,
    main_token: str,
) -> None:
    if agents is None:
        return
    if not isinstance(agents, list):
        _issue(
            issues,
            "error",
            "invalid_agents_registry",
            "agents.json must contain a JSON list.",
            path=str(path),
        )
        return

    seen_names: set[str] = set()
    seen_tokens: dict[str, str] = {}
    if main_token and not _is_placeholder(main_token):
        seen_tokens[main_token] = "main"

    for agent in agents:
        if not isinstance(agent, dict):
            _issue(
                issues,
                "error",
                "invalid_agent_entry",
                "Each agent entry in agents.json must be an object.",
                path=str(path),
            )
            continue

        name = str(agent.get("name", "")).strip()
        label = f"Agent '{name or '?'}'"
        if not name:
            _issue(issues, "error", "agent_name_missing", "Sub-agent name is missing.", path=str(path))
            continue
        if name in seen_names:
            _issue(
                issues,
                "error",
                "duplicate_agent_name",
                f"Duplicate sub-agent name '{name}' in agents.json.",
                path=str(path),
            )
        seen_names.add(name)

        transports = _active_transports(agent)
        if "telegram" in transports:
            _validate_telegram_config(
                agent,
                issues,
                prefix=label,
                code_prefix=f"agent_{name}",
                path=str(path),
            )

        token = str(agent.get("telegram_token", "")).strip()
        if token and not _is_placeholder(token):
            owner = seen_tokens.get(token)
            if owner is not None:
                _issue(
                    issues,
                    "warning",
                    "duplicate_telegram_token",
                    f"{label} reuses the Telegram token already assigned to '{owner}'.",
                    path=str(path),
                )
            else:
                seen_tokens[token] = name


def _validate_cron_jobs(home: Path, jobs: Any, issues: list[PreflightIssue], *, path: Path) -> None:
    if jobs is None:
        return
    entries = jobs.get("jobs") if isinstance(jobs, dict) else jobs
    if not isinstance(entries, list):
        _issue(
            issues,
            "error",
            "invalid_cron_registry",
            "cron_jobs.json must contain a list or an object with a 'jobs' list.",
            path=str(path),
        )
        return

    cron_dir = home / "workspace" / "cron_tasks"
    for entry in entries:
        if not isinstance(entry, dict):
            _issue(
                issues,
                "error",
                "invalid_cron_entry",
                "Each cron job entry must be an object.",
                path=str(path),
            )
            continue
        folder = str(entry.get("task_folder", "")).strip()
        if not folder:
            continue
        if not (cron_dir / folder).is_dir():
            _issue(
                issues,
                "error",
                "missing_cron_task_folder",
                f"Cron job '{entry.get('id', folder)}' points to missing task folder '{folder}'.",
                path=str(path),
            )


def run_runtime_preflight(ductor_home: str | Path) -> PreflightReport:
    """Validate runtime layout, config, sub-agents, and cron registry."""
    home = Path(ductor_home).expanduser().resolve()
    issues: list[PreflightIssue] = []

    workspace = home / "workspace"
    if not workspace.is_dir():
        _issue(
            issues,
            "error",
            "missing_workspace",
            "Runtime workspace directory is missing.",
            path=str(workspace),
        )

    config_path = home / "config" / "config.json"
    config_data = _load_json(config_path, issues, required=True)
    main_token = ""
    if isinstance(config_data, dict):
        _validate_main_config(config_data, issues, config_path)
        main_token = str(config_data.get("telegram_token", "")).strip()

    agents_path = home / "agents.json"
    agents_data = _load_json(agents_path, issues, required=False)
    _validate_agents_registry(agents_data, issues, path=agents_path, main_token=main_token)

    cron_jobs_path = home / "cron_jobs.json"
    cron_jobs = _load_json(cron_jobs_path, issues, required=False)
    _validate_cron_jobs(home, cron_jobs, issues, path=cron_jobs_path)

    return PreflightReport(ductor_home=home, issues=issues)


def render_preflight_report(report: PreflightReport) -> str:
    """Render a compact human-readable report."""
    lines = [f"Runtime: {report.ductor_home}"]
    if report.ok:
        lines.append("OK: no preflight issues found.")
        return "\n".join(lines)

    for issue in report.issues:
        location = f" [{issue.path}]" if issue.path else ""
        lines.append(f"{issue.severity.upper()} {issue.code}:{location} {issue.message}")
    return "\n".join(lines)
