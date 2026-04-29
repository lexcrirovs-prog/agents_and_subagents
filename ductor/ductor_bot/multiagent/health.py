"""Agent health tracking for the supervisor."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Literal


@dataclass(slots=True)
class AgentHealth:
    """Runtime health state for a single agent."""

    name: str
    status: Literal["running", "starting", "crashed", "stopped"] = "stopped"
    ready: bool = False
    started_at: float = 0.0
    restart_count: int = 0
    last_crash_time: float = 0.0
    last_crash_error: str = ""

    @property
    def uptime_seconds(self) -> float:
        if self.status != "running" or self.started_at == 0.0:
            return 0.0
        return time.monotonic() - self.started_at

    @property
    def uptime_human(self) -> str:
        secs = self.uptime_seconds
        if secs < 60:
            return f"{secs:.0f}s"
        if secs < 3600:
            return f"{secs / 60:.0f}m"
        hours = secs / 3600
        if hours < 24:
            return f"{hours:.1f}h"
        return f"{hours / 24:.1f}d"

    def mark_starting(self) -> None:
        self.status = "starting"
        self.ready = False

    def mark_running(self) -> None:
        self.status = "running"
        self.ready = False
        self.started_at = time.monotonic()
        self.restart_count = 0

    def mark_ready(self) -> None:
        if self.status == "running":
            self.ready = True

    def mark_crashed(self, error: str) -> None:
        self.status = "crashed"
        self.ready = False
        self.restart_count += 1
        self.last_crash_time = time.monotonic()
        self.last_crash_error = error

    def mark_stopped(self) -> None:
        self.status = "stopped"
        self.ready = False
        self.started_at = 0.0
