"""Structured external checkpoint for long-running background tasks."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from ductor_bot.infra.json_store import atomic_json_save, load_json
from ductor_bot.tasks.models import TaskEntry

_LIST_LIMIT = 8
_TEXT_LIMIT = 400


def initial_work_state(entry: TaskEntry, prompt: str) -> dict[str, Any]:
    now = time.time()
    return {
        "schema_version": 1,
        "task_id": entry.task_id,
        "task_name": entry.name,
        "parent_agent": entry.parent_agent,
        "status": entry.status,
        "goal": _trim(prompt),
        "current_phase": "created",
        "done": [],
        "next_step": "Start the task and record milestones here.",
        "open_questions": [],
        "key_files": [],
        "artifacts": [],
        "resume_prompt": "",
        "last_result_preview": "",
        "last_error": "",
        "created_at": now,
        "updated_at": now,
    }


def load_work_state(path: Path) -> dict[str, Any]:
    raw = load_json(path)
    if isinstance(raw, dict):
        return raw
    return {}


def save_work_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_json_save(path, state)


def sync_work_state(
    path: Path,
    *,
    entry: TaskEntry | None = None,
    prompt: str | None = None,
    status: str | None = None,
    phase: str | None = None,
    done: str | list[str] | None = None,
    next_step: str | None = None,
    question: str | None = None,
    clear_questions: bool = False,
    key_files: list[str] | None = None,
    artifacts: list[str] | None = None,
    resume_prompt: str | None = None,
    result_preview: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    state = load_work_state(path)
    if not state:
        if entry is None:
            msg = "entry is required to seed a new work state"
            raise ValueError(msg)
        state = initial_work_state(entry, prompt or entry.original_prompt)

    if entry is not None:
        state.setdefault("schema_version", 1)
        state["task_id"] = entry.task_id
        state["task_name"] = entry.name
        state["parent_agent"] = entry.parent_agent
        state.setdefault("created_at", entry.created_at)
        if prompt:
            state["goal"] = _trim(prompt)

    if status is not None:
        state["status"] = status
        state["current_phase"] = phase or _phase_for_status(status)
    elif phase is not None:
        state["current_phase"] = phase

    if done:
        items = [done] if isinstance(done, str) else done
        state["done"] = _append_unique(state.get("done"), items)

    if next_step is not None:
        state["next_step"] = _trim(next_step)

    if clear_questions:
        state["open_questions"] = []
    elif question:
        state["open_questions"] = _append_unique(state.get("open_questions"), [question])

    if key_files:
        state["key_files"] = _append_unique(state.get("key_files"), key_files)
    if artifacts:
        state["artifacts"] = _append_unique(state.get("artifacts"), artifacts)

    if resume_prompt is not None:
        state["resume_prompt"] = _trim(resume_prompt)
    if result_preview is not None:
        state["last_result_preview"] = _trim(result_preview)
    if error is not None:
        state["last_error"] = _trim(error)

    state["updated_at"] = time.time()
    save_work_state(path, state)
    return state


def render_work_state_handoff(path: Path) -> str:
    state = load_work_state(path)
    if not state:
        return ""

    lines = ["WORKSTATE CHECKPOINT:"]
    _add_line(lines, "Task", state.get("task_name"))
    _add_line(lines, "Status", state.get("status"))
    _add_line(lines, "Current phase", state.get("current_phase"))
    _add_line(lines, "Goal", state.get("goal"))

    done = _render_list(state.get("done"))
    if done:
        lines.append("Completed milestones:")
        lines.extend(done)

    questions = _render_list(state.get("open_questions"))
    if questions:
        lines.append("Open questions:")
        lines.extend(questions)

    _add_line(lines, "Next step", state.get("next_step"))

    key_files = _render_list(state.get("key_files"))
    if key_files:
        lines.append("Key files:")
        lines.extend(key_files)

    artifacts = _render_list(state.get("artifacts"))
    if artifacts:
        lines.append("Artifacts:")
        lines.extend(artifacts)

    _add_line(lines, "Last result preview", state.get("last_result_preview"))
    _add_line(lines, "Last error", state.get("last_error"))
    _add_line(lines, "Last resume prompt", state.get("resume_prompt"))
    return "\n".join(lines)


def _phase_for_status(status: str) -> str:
    mapping = {
        "running": "running",
        "waiting": "waiting-for-parent",
        "done": "completed",
        "failed": "failed",
        "cancelled": "cancelled",
    }
    return mapping.get(status, status)


def _append_unique(existing: Any, items: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in existing or []:
        text = _trim(str(raw))
        if text and text not in seen:
            result.append(text)
            seen.add(text)
    for raw in items:
        text = _trim(raw)
        if text and text not in seen:
            result.append(text)
            seen.add(text)
    return result[-_LIST_LIMIT:]


def _render_list(raw: Any) -> list[str]:
    items: list[str] = []
    for item in raw or []:
        text = _trim(str(item))
        if text:
            items.append(f"- {text}")
    return items[-_LIST_LIMIT:]


def _add_line(lines: list[str], label: str, value: Any) -> None:
    text = _trim(str(value or ""))
    if text:
        lines.append(f"{label}: {text}")


def _trim(value: str) -> str:
    text = " ".join(value.strip().split())
    if len(text) > _TEXT_LIMIT:
        return text[: _TEXT_LIMIT - 3] + "..."
    return text
