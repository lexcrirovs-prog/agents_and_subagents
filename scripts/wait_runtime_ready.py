#!/usr/bin/env python3
"""Wait until the main runtime reports itself ready via the internal API."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

_DEFAULT_PORT = 8799


def _default_home() -> Path:
    root = Path(__file__).resolve().parents[1]
    return (root / "runtime-template").resolve()


def _parse_port(raw: str | None) -> int | None:
    try:
        port = int(str(raw or "").strip())
    except ValueError:
        return None
    return port if 0 < port < 65536 else None


def _resolve_port(home: Path) -> int:
    env_port = _parse_port(os.environ.get("DUCTOR_INTERAGENT_PORT"))
    if env_port is not None:
        return env_port

    port_file = home / "internal_api_port.txt"
    if port_file.is_file():
        try:
            port = _parse_port(port_file.read_text(encoding="utf-8"))
        except OSError:
            port = None
        if port is not None:
            return port

    config_path = home / "config" / "config.json"
    if config_path.is_file():
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
        port = _parse_port(str(data.get("interagent_port", "")))
        if port is not None:
            return port

    return _DEFAULT_PORT


def _is_ready(payload: dict[str, object]) -> bool:
    runtime = payload.get("runtime")
    agents = payload.get("agents")
    if not isinstance(runtime, dict) or not isinstance(agents, dict):
        return False
    main = agents.get("main")
    if not isinstance(main, dict):
        return False
    return bool(runtime.get("main_ready")) and main.get("status") == "running" and bool(
        main.get("ready")
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", default=str(_default_home()), help="Path to DUCTOR_HOME")
    parser.add_argument("--timeout", type=float, default=30.0, help="Max seconds to wait")
    parser.add_argument("--interval", type=float, default=1.0, help="Polling interval seconds")
    parser.add_argument("--quiet", action="store_true", help="Suppress success output")
    args = parser.parse_args()

    home = Path(args.home).expanduser().resolve()
    host = os.environ.get("DUCTOR_INTERAGENT_HOST", "127.0.0.1").strip() or "127.0.0.1"
    port = _resolve_port(home)
    url = f"http://{host}:{port}/interagent/health"
    deadline = time.monotonic() + max(args.timeout, 0.0)
    last_error = ""

    while True:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                payload = json.loads(response.read().decode())
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = str(exc)
        else:
            if _is_ready(payload):
                if not args.quiet:
                    print(f"READY {url}")
                return 0
            last_error = json.dumps(payload, ensure_ascii=False)

        if time.monotonic() >= deadline:
            print(f"NOT READY {url}: {last_error}", file=sys.stderr)
            return 1
        time.sleep(max(args.interval, 0.1))


if __name__ == "__main__":
    raise SystemExit(main())
