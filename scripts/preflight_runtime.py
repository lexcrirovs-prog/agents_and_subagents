#!/usr/bin/env python3
"""Check runtime configuration, tokens, agent registry, and cron integrity."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _default_home() -> Path:
    root = Path(__file__).resolve().parents[1]
    return (root / "runtime-template").resolve()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", default=str(_default_home()), help="Path to DUCTOR_HOME")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return a non-zero exit code when any issue is found.",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    framework_root = root / "ductor"
    if str(framework_root) not in sys.path:
        sys.path.insert(0, str(framework_root))

    from ductor_bot.infra.preflight import render_preflight_report, run_runtime_preflight

    report = run_runtime_preflight(args.home)
    print(render_preflight_report(report))
    if args.strict and report.issues:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
