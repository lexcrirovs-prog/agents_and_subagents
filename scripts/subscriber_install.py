#!/usr/bin/env python3
"""Bootstrap and configure a subscriber runtime in a guided, install-safe way."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
FRAMEWORK_ROOT = ROOT_DIR / "ductor"
DEFAULT_RUNTIME_HOME = ROOT_DIR / "runtime-template"
MIN_PYTHON = (3, 11)
_AUTHENTICATED = "authenticated"
_WINDOWS_DETACH_FLAGS = (
    getattr(subprocess, "DETACHED_PROCESS", 0)
    | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    | getattr(subprocess, "CREATE_NO_WINDOW", 0)
)


@dataclass(frozen=True)
class ProviderChoice:
    provider: str
    model: str
    reasoning_effort: str
    executable: str


@dataclass(frozen=True)
class ProviderAuth:
    provider: str
    status: str


PROVIDER_DEFAULTS: dict[str, ProviderChoice] = {
    "codex": ProviderChoice(
        provider="codex",
        model="gpt-5.4",
        reasoning_effort="high",
        executable="codex",
    ),
    "claude": ProviderChoice(
        provider="claude",
        model="sonnet",
        reasoning_effort="medium",
        executable="claude",
    ),
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=sorted(PROVIDER_DEFAULTS), help="Preferred provider")
    parser.add_argument("--telegram-token", help="Telegram bot token")
    parser.add_argument("--timezone", help="IANA timezone, for example Europe/Berlin")
    parser.add_argument("--owner-user-id", type=int, help="Telegram owner user id")
    parser.add_argument(
        "--pair-timeout",
        type=int,
        default=180,
        help="Seconds to wait for Telegram owner pairing when owner id is not supplied.",
    )
    parser.add_argument(
        "--runtime-home",
        default=str(DEFAULT_RUNTIME_HOME),
        help="Path to the runtime home to configure",
    )
    parser.add_argument(
        "--bootstrap-only",
        action="store_true",
        help="Only create the venv, install ductor, and refresh the runtime template.",
    )
    parser.add_argument(
        "--no-start",
        action="store_true",
        help="Do not start the runtime automatically after configuration.",
    )
    parser.add_argument(
        "--ready-timeout",
        type=int,
        default=45,
        help="Seconds to wait for runtime readiness after auto-start.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Accept detected defaults without additional confirmation where possible.",
    )
    return parser.parse_args()


def _ensure_python_version() -> None:
    if sys.version_info < MIN_PYTHON:
        version = ".".join(str(part) for part in MIN_PYTHON)
        msg = f"Python {version}+ is required."
        raise SystemExit(msg)


def _ensure_command(name: str) -> str:
    path = shutil.which(name)
    if path:
        return path
    raise SystemExit(f"Required command not found in PATH: {name}")


def _run(cmd: list[str], *, cwd: Path | None = None) -> None:
    subprocess.run(cmd, cwd=cwd, check=True)


def _venv_bin_dir(root: Path) -> Path:
    posix_bin = root / ".venv" / "bin"
    windows_bin = root / ".venv" / "Scripts"
    if posix_bin.is_dir():
        return posix_bin
    return windows_bin


def _venv_python(root: Path) -> Path:
    for candidate in (
        root / ".venv" / "bin" / "python",
        root / ".venv" / "Scripts" / "python.exe",
        root / ".venv" / "Scripts" / "python",
    ):
        if candidate.is_file():
            return candidate
    msg = f"Virtualenv python not found under {root / '.venv'}"
    raise SystemExit(msg)


def _runtime_env(root: Path, runtime_home: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["DUCTOR_HOME"] = str(runtime_home)
    env["DUCTOR_FRAMEWORK_ROOT"] = str(FRAMEWORK_ROOT)
    bin_dir = str(_venv_bin_dir(root))
    current_path = env.get("PATH", "")
    env["PATH"] = bin_dir if not current_path else f"{bin_dir}{os.pathsep}{current_path}"
    return env


def _run_json(cmd: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> object:
    result = subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Failed to parse JSON from command: {' '.join(cmd)}") from exc


def _ensure_venv(root: Path) -> None:
    if not (root / ".venv").exists():
        _run([sys.executable, "-m", "venv", str(root / ".venv")])
    venv_python = _venv_python(root)
    _run([str(venv_python), "-m", "pip", "install", "--upgrade", "pip"])
    _run([str(venv_python), "-m", "pip", "install", "-e", str(root / "ductor")])


def _refresh_runtime_template(root: Path) -> None:
    venv_python = _venv_python(root)
    _run([str(venv_python), str(root / "scripts" / "sync_runtime_template.py")], cwd=root)
    _run([str(venv_python), str(root / "scripts" / "render_agent_templates.py")], cwd=root)


def _seed_runtime_home(runtime_home: Path) -> None:
    source = DEFAULT_RUNTIME_HOME.resolve()
    if runtime_home == source:
        return
    shutil.copytree(source, runtime_home, dirs_exist_ok=True)


def _authenticated_providers(root: Path) -> dict[str, ProviderAuth]:
    code = f"""
import json
import sys
sys.path.insert(0, {str(FRAMEWORK_ROOT)!r})
from ductor_bot.cli.auth import check_claude_auth, check_codex_auth

results = {{}}
for probe in (check_codex_auth(), check_claude_auth()):
    results[probe.provider] = {{
        "provider": probe.provider,
        "status": probe.status.value,
    }}
print(json.dumps(results))
"""
    payload = _run_json([str(_venv_python(root)), "-c", code], cwd=root)
    if not isinstance(payload, dict):
        raise SystemExit("Provider auth probe returned an invalid payload.")
    out: dict[str, ProviderAuth] = {}
    for name, item in payload.items():
        if not isinstance(name, str) or not isinstance(item, dict):
            continue
        provider = str(item.get("provider", name))
        status = str(item.get("status", "not_found"))
        out[name] = ProviderAuth(provider=provider, status=status)
    return out


def _authenticated_provider_names(results: dict[str, ProviderAuth]) -> list[str]:
    return [name for name, result in results.items() if result.status == _AUTHENTICATED]


def _select_provider(
    preferred: str | None,
    results: dict[str, ProviderAuth],
    *,
    accept_defaults: bool,
) -> ProviderChoice:
    if preferred:
        result = results.get(preferred)
        if result is None or result.status != _AUTHENTICATED:
            raise SystemExit(
                f"Provider '{preferred}' is not authenticated locally. Authenticate it first."
            )
        return PROVIDER_DEFAULTS[preferred]

    authenticated = _authenticated_provider_names(results)
    if not authenticated:
        raise SystemExit(
            "No authenticated provider found. Authenticate Codex or Claude locally first."
        )
    if len(authenticated) == 1:
        return PROVIDER_DEFAULTS[authenticated[0]]
    if accept_defaults:
        return PROVIDER_DEFAULTS["codex"]

    print("Both Codex and Claude are authenticated.")
    print("Recommended default: codex")
    while True:
        choice = input("Choose provider [codex/claude]: ").strip().lower()
        if choice in PROVIDER_DEFAULTS:
            return PROVIDER_DEFAULTS[choice]
        print("Please enter 'codex' or 'claude'.")


def _prompt_value(prompt: str, *, default: str = "", accept_defaults: bool = False) -> str:
    if accept_defaults and default:
        return default
    suffix = f" [{default}]" if default else ""
    while True:
        value = input(f"{prompt}{suffix}: ").strip()
        if value:
            return value
        if default:
            return default


def _detect_timezone() -> str:
    return str(
        getattr(getattr(__import__("datetime"), "datetime").now().astimezone(), "tzinfo", "UTC")
        or "UTC"
    )


def _validate_telegram_token(token: str) -> tuple[str, str]:
    payload = _telegram_api(token, "getMe")
    result = payload.get("result", {})
    username = str(result.get("username", "")).strip()
    bot_id = str(result.get("id", "")).strip()
    if not username:
        raise SystemExit("Telegram token validation succeeded but bot username is missing.")
    return username, bot_id


def _telegram_api(token: str, method: str, data: dict[str, object] | None = None) -> dict[str, object]:
    encoded = urllib.parse.quote(token, safe="")
    url = f"https://api.telegram.org/bot{encoded}/{method}"
    raw_data: bytes | None = None
    headers = {}
    if data is not None:
        raw_data = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    try:
        request = urllib.request.Request(url, data=raw_data, headers=headers, method="POST")
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise SystemExit(f"Telegram API call failed for {method}: {exc}") from exc

    if not payload.get("ok"):
        description = payload.get("description", "unknown Telegram API error")
        raise SystemExit(f"Telegram API {method} failed: {description}")
    return payload


def _pair_command_matches(text: str, code: str) -> bool:
    stripped = text.strip()
    if not stripped.startswith("/pair"):
        return False
    parts = stripped.split()
    if len(parts) < 2:
        return False
    command = parts[0].split("@", 1)[0]
    return command == "/pair" and parts[1] == code


def _next_update_offset(token: str) -> int:
    payload = _telegram_api(token, "getUpdates", {"timeout": 0, "limit": 100})
    updates = payload.get("result", [])
    if not isinstance(updates, list) or not updates:
        return 0
    max_update = max(int(update.get("update_id", 0)) for update in updates)
    return max_update + 1


def _pair_owner_via_telegram(
    token: str,
    *,
    bot_username: str,
    timeout_seconds: int,
) -> int:
    code = secrets.token_hex(3).upper()
    offset = _next_update_offset(token)
    deadline = time.time() + timeout_seconds
    print()
    print("== Telegram Pairing ==")
    print(f"Open https://t.me/{bot_username} and send this message in private chat:")
    print(f"/pair {code}")
    print("Waiting for the first valid private-chat pairing message...")

    while time.time() < deadline:
        remaining = max(1, int(deadline - time.time()))
        payload = _telegram_api(
            token,
            "getUpdates",
            {
                "timeout": min(20, remaining),
                "offset": offset,
                "allowed_updates": ["message"],
            },
        )
        updates = payload.get("result", [])
        if not isinstance(updates, list):
            continue

        for update in updates:
            offset = max(offset, int(update.get("update_id", 0)) + 1)
            message = update.get("message")
            if not isinstance(message, dict):
                continue
            chat = message.get("chat")
            from_user = message.get("from")
            text = str(message.get("text", "")).strip()
            if not isinstance(chat, dict) or not isinstance(from_user, dict):
                continue
            if str(chat.get("type", "")) != "private":
                continue
            if not _pair_command_matches(text, code):
                continue
            user_id = from_user.get("id")
            if isinstance(user_id, int):
                return user_id

    raise SystemExit(
        "Telegram pairing timed out. Re-run the installer or provide --owner-user-id explicitly."
    )


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict[str, object]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _set_env_value(env_path: Path, key: str, value: str) -> None:
    lines: list[str] = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()
    else:
        example = env_path.with_name(".env.example")
        if example.exists():
            lines = example.read_text(encoding="utf-8").splitlines()

    replaced = False
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(f"{key}=") or stripped.startswith(f"export {key}="):
            out.append(f"{key}={value}")
            replaced = True
        else:
            out.append(line)

    if not replaced:
        if out and out[-1].strip():
            out.append("")
        out.append(f"{key}={value}")

    env_path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")


def _configure_runtime(
    runtime_home: Path,
    provider: ProviderChoice,
    *,
    timezone: str,
    owner_user_id: int | None,
) -> Path:
    config_path = runtime_home / "config" / "config.json"
    config = _load_json(config_path)
    config["provider"] = provider.provider
    config["model"] = provider.model
    config["reasoning_effort"] = provider.reasoning_effort
    config["user_timezone"] = timezone
    config["transport"] = "telegram"
    config["transports"] = ["telegram"]
    config["telegram_token"] = "env:DUCTOR_TELEGRAM_TOKEN"
    config["allowed_group_ids"] = []
    config["group_mention_only"] = False
    config["allowed_user_ids"] = [owner_user_id] if owner_user_id is not None else []
    _write_json(config_path, config)
    example_path = runtime_home / "config" / "config.example.json"
    _write_json(example_path, config)
    return config_path


def _print_auth_status(results: dict[str, ProviderAuth]) -> None:
    print("== Provider Auth ==")
    for name, result in results.items():
        print(f"{name}: {result.status}")
    print()


def _print_report(root: Path, home: Path) -> None:
    cmd = [
        str(_venv_python(root)),
        str(root / "scripts" / "preflight_runtime.py"),
        "--home",
        str(home),
        "--strict",
    ]
    subprocess.run(cmd, cwd=root, env=_runtime_env(root, home), check=True)


def _runtime_is_ready(root: Path, runtime_home: Path) -> bool:
    cmd = [
        str(_venv_python(root)),
        str(root / "scripts" / "wait_runtime_ready.py"),
        "--home",
        str(runtime_home),
        "--timeout",
        "2",
        "--quiet",
    ]
    result = subprocess.run(
        cmd,
        cwd=root,
        env=_runtime_env(root, runtime_home),
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def _start_runtime(root: Path, runtime_home: Path) -> Path:
    env = _runtime_env(root, runtime_home)
    log_path = runtime_home / "logs" / "installer-start.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    kwargs: dict[str, object] = {
        "cwd": root,
        "env": env,
        "stdout": None,
        "stderr": subprocess.STDOUT,
    }
    if os.name == "nt":
        kwargs["creationflags"] = _WINDOWS_DETACH_FLAGS
    else:
        kwargs["start_new_session"] = True
    with log_path.open("ab") as handle:
        kwargs["stdout"] = handle
        subprocess.Popen([str(_venv_python(root)), "-m", "ductor_bot"], **kwargs)
    return log_path


def _wait_for_runtime_ready(root: Path, runtime_home: Path, *, timeout_seconds: int) -> None:
    cmd = [
        str(_venv_python(root)),
        str(root / "scripts" / "wait_runtime_ready.py"),
        "--home",
        str(runtime_home),
        "--timeout",
        str(timeout_seconds),
    ]
    subprocess.run(cmd, cwd=root, env=_runtime_env(root, runtime_home), check=True)


def _send_ready_ping(token: str, owner_user_id: int, provider: ProviderChoice) -> None:
    _telegram_api(
        token,
        "sendMessage",
        {
            "chat_id": owner_user_id,
            "text": (
                "Runtime installed and running.\n"
                f"Provider: {provider.provider}\n"
                "You can now send a normal message to start working."
            ),
        },
    )


def main() -> int:
    _ensure_python_version()
    args = _parse_args()

    root = ROOT_DIR
    runtime_home = Path(args.runtime_home).expanduser().resolve()

    _ensure_command("git")
    _ensure_command("node")
    _ensure_command("npm")

    _ensure_venv(root)
    _refresh_runtime_template(root)

    if args.bootstrap_only:
        print("Bootstrap complete.")
        return 0

    auth_results = _authenticated_providers(root)
    _print_auth_status(auth_results)
    provider = _select_provider(args.provider, auth_results, accept_defaults=args.yes)
    _ensure_command(provider.executable)

    token = args.telegram_token or os.environ.get("DUCTOR_TELEGRAM_TOKEN", "").strip()
    if not token:
        token = _prompt_value(
            "Enter Telegram bot token",
            accept_defaults=args.yes,
        )

    timezone = args.timezone or _prompt_value(
        "Enter timezone",
        default=_detect_timezone(),
        accept_defaults=args.yes,
    )

    username, bot_id = _validate_telegram_token(token)
    print(f"Telegram bot validated: @{username} (id={bot_id})")

    owner_user_id = args.owner_user_id
    if owner_user_id is None:
        owner_user_id = _pair_owner_via_telegram(
            token,
            bot_username=username,
            timeout_seconds=args.pair_timeout,
        )
        print(f"Paired Telegram owner user id: {owner_user_id}")

    _seed_runtime_home(runtime_home)
    runtime_home.mkdir(parents=True, exist_ok=True)
    env_path = runtime_home / ".env"
    _set_env_value(env_path, "DUCTOR_TELEGRAM_TOKEN", token)
    config_path = _configure_runtime(
        runtime_home,
        provider,
        timezone=timezone,
        owner_user_id=owner_user_id,
    )
    print(f"Configured runtime: {config_path}")
    print()
    print("== Strict Preflight ==")
    _print_report(root, runtime_home)
    if not args.no_start:
        print()
        print("== Runtime Start ==")
        if _runtime_is_ready(root, runtime_home):
            print("Runtime is already running.")
        else:
            log_path = _start_runtime(root, runtime_home)
            _wait_for_runtime_ready(root, runtime_home, timeout_seconds=args.ready_timeout)
            print(f"Runtime started. Logs: {log_path}")
        _send_ready_ping(token, owner_user_id, provider)
        print(f"Telegram readiness ping sent to user id {owner_user_id}.")
    print()
    print("Install is ready.")
    print(f"Owner user id configured: {owner_user_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
