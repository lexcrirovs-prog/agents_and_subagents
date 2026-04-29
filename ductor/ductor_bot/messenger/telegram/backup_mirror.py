"""Telegram backup-mirror reminder and callback helpers."""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from ductor_bot.messenger.telegram.sender import SendRichOpts, send_rich

if TYPE_CHECKING:
    from ductor_bot.messenger.telegram.app import TelegramBot

PROMPT_TOKEN = "BACKUP_MIRROR_REMINDER_V1"
CALLBACK_PREFIX = "bkp:"
ACTION_REFRESH = "yes"
ACTION_SKIP = "no"
BUTTON_REFRESH = "Сделать"
BUTTON_SKIP = "Не делать"

_STATE_FILE = "backup_mirror_reminder_state.json"
_HISTORY_LIMIT = 30


def is_backup_reminder_prompt(result_text: str) -> bool:
    """Return True when cron output contains the reminder sentinel."""
    if not result_text:
        return False
    return any(line.strip() == PROMPT_TOKEN for line in result_text.splitlines())


def is_backup_callback(data: str) -> bool:
    """Return True for backup reminder callback payloads."""
    return data.startswith(CALLBACK_PREFIX)


def parse_backup_callback(data: str) -> tuple[str, str] | None:
    """Parse ``bkp:<action>:<prompt_date>`` callback data."""
    if not is_backup_callback(data):
        return None
    parts = data.split(":", 2)
    if len(parts) != 3:
        return None
    _, action, prompt_date = parts
    if action not in {ACTION_REFRESH, ACTION_SKIP} or not prompt_date:
        return None
    return action, prompt_date


def get_backup_callback_label(data: str) -> str | None:
    """Return the Russian button label for a backup callback payload."""
    parsed = parse_backup_callback(data)
    if parsed is None:
        return None
    action, _prompt_date = parsed
    return BUTTON_REFRESH if action == ACTION_REFRESH else BUTTON_SKIP


def build_backup_prompt_text() -> str:
    """Return the user-facing Telegram reminder text."""
    return "Вечерний контроль.\n\nОбновить GitHub backup mirror?"


def build_backup_prompt_markup(prompt_date: str) -> InlineKeyboardMarkup:
    """Return inline buttons for the nightly backup reminder."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=BUTTON_REFRESH,
                    callback_data=f"{CALLBACK_PREFIX}{ACTION_REFRESH}:{prompt_date}",
                ),
                InlineKeyboardButton(
                    text=BUTTON_SKIP,
                    callback_data=f"{CALLBACK_PREFIX}{ACTION_SKIP}:{prompt_date}",
                ),
            ]
        ]
    )


async def deliver_backup_reminder(
    bot: TelegramBot,
    chat_id: int,
    *,
    thread_id: int | None = None,
) -> None:
    """Send the nightly reminder with Telegram inline buttons."""
    prompt_date = _today_local(bot.config.user_timezone)
    await asyncio.to_thread(_record_prompt_delivery, _state_path(bot), prompt_date)
    await send_rich(
        bot.bot_instance,
        chat_id,
        build_backup_prompt_text(),
        SendRichOpts(
            allowed_roots=bot.file_roots(bot._orch.paths),
            reply_markup=build_backup_prompt_markup(prompt_date),
            thread_id=thread_id,
        ),
    )


async def broadcast_backup_reminder(bot: TelegramBot) -> None:
    """Broadcast the nightly reminder to every allowed Telegram user."""
    for user_id in bot.config.allowed_user_ids:
        await deliver_backup_reminder(bot, user_id)


async def handle_backup_callback(
    bot: TelegramBot,
    chat_id: int,
    data: str,
    *,
    thread_id: int | None = None,
) -> None:
    """Handle reminder callbacks for backup refresh and skip."""
    parsed = parse_backup_callback(data)
    if parsed is None:
        return
    action, prompt_date = parsed

    state_path = _state_path(bot)
    state = await asyncio.to_thread(_load_state, state_path)
    entry = state.get("history", {}).get(prompt_date, {})

    if action == ACTION_SKIP:
        if entry.get("status") == "skipped":
            await _send_info(
                bot,
                chat_id,
                "Пропуск уже зафиксирован. Больше ничего не делаю.",
                thread_id=thread_id,
            )
            return
        if entry.get("status") == "success":
            await _send_info(
                bot,
                chat_id,
                "Mirror уже обновлён по этому напоминанию. Пропускать поздно.",
                thread_id=thread_id,
            )
            return
        await asyncio.to_thread(
            _record_result,
            state_path,
            prompt_date,
            status="skipped",
            action="skip",
        )
        await _send_info(
            bot,
            chat_id,
            "Пропуск зафиксирован. Сегодня backup mirror не обновляю.",
            thread_id=thread_id,
        )
        return

    if bot._backup_refresh_lock.locked():
        await _send_info(
            bot,
            chat_id,
            "Обновление уже выполняется. Дублировать ход не буду.",
            thread_id=thread_id,
        )
        return

    if entry.get("status") == "success":
        await _send_info(
            bot,
            chat_id,
            "Этот nightly backup уже выполнен. Второй раз гонять его не нужно.",
            thread_id=thread_id,
        )
        return

    await _send_info(
        bot,
        chat_id,
        "Принято. Обновляю backup mirror и отправляю изменения в GitHub.",
        thread_id=thread_id,
    )

    async with bot._backup_refresh_lock:
        await asyncio.to_thread(
            _record_result,
            state_path,
            prompt_date,
            status="running",
            action="refresh",
        )
        summary = await _run_backup_refresh(bot)
        if summary["ok"]:
            await asyncio.to_thread(
                _record_result,
                state_path,
                prompt_date,
                status="success",
                action="refresh",
                details=summary,
            )
            await _send_info(
                bot,
                chat_id,
                _format_success(summary),
                thread_id=thread_id,
            )
            return

        await asyncio.to_thread(
            _record_result,
            state_path,
            prompt_date,
            status="failed",
            action="refresh",
            details=summary,
        )
        await _send_info(
            bot,
            chat_id,
            _format_failure(summary),
            thread_id=thread_id,
        )


async def _run_backup_refresh(bot: TelegramBot) -> dict[str, Any]:
    """Execute the sanitized refresh script and parse its JSON result."""
    script = _script_path(bot)
    if not script.is_file():
        return {
            "ok": False,
            "error": f"refresh script not found: {script}",
        }

    process = await asyncio.create_subprocess_exec(
        sys.executable,
        str(script),
        "--push",
        "--json",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout_bytes, stderr_bytes = await process.communicate()
    stdout = stdout_bytes.decode("utf-8", errors="replace").strip()
    stderr = stderr_bytes.decode("utf-8", errors="replace").strip()

    if process.returncode != 0:
        return {
            "ok": False,
            "error": stderr or stdout or f"exit code {process.returncode}",
            "returncode": process.returncode,
        }

    try:
        payload = json.loads(stdout) if stdout else {}
    except json.JSONDecodeError as exc:
        return {
            "ok": False,
            "error": f"invalid JSON from refresh script: {exc}",
            "stdout": stdout[-500:],
            "stderr": stderr[-500:],
        }

    payload["ok"] = True
    return payload


async def _send_info(
    bot: TelegramBot,
    chat_id: int,
    text: str,
    *,
    thread_id: int | None = None,
) -> None:
    await send_rich(
        bot.bot_instance,
        chat_id,
        text,
        SendRichOpts(
            allowed_roots=bot.file_roots(bot._orch.paths),
            thread_id=thread_id,
        ),
    )


def _format_success(summary: dict[str, Any]) -> str:
    changed = bool(summary.get("changed"))
    if not changed:
        return (
            "Sanitized backup mirror проверен и синхронизирован.\n\n"
            "Изменений не было, новый commit не понадобился."
        )

    commit = str(summary.get("commit", "") or "")[:12]
    pushed = bool(summary.get("pushed"))
    synced_roots = summary.get("synced_roots", [])
    roots_line = ", ".join(str(item) for item in synced_roots[:5])
    if len(synced_roots) > 5:
        roots_line += ", ..."
    push_line = "Изменения отправлены в `origin/main`." if pushed else "Push не выполнялся."
    return (
        "Sanitized backup mirror обновлён.\n\n"
        f"Commit: `{commit or 'local-only'}`\n"
        f"Корни: {roots_line or 'без списка'}\n"
        f"{push_line}"
    )


def _format_failure(summary: dict[str, Any]) -> str:
    error = str(summary.get("error") or "неизвестная ошибка")
    return (
        "Backup refresh не завершился.\n\n"
        f"Причина: {error[:1000]}\n"
        "Mirror и GitHub оставил без новых изменений."
    )


def _script_path(bot: TelegramBot) -> Path:
    return bot._orch.paths.ductor_home.parent.parent / "scripts" / "refresh_private_backup.py"


def _state_path(bot: TelegramBot) -> Path:
    return bot._orch.paths.ductor_home / _STATE_FILE


def _today_local(timezone_name: str) -> str:
    tz = ZoneInfo(timezone_name or "UTC")
    return datetime.now(tz).date().isoformat()


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _load_state(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"history": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"history": {}}
    if not isinstance(data, dict):
        return {"history": {}}
    history = data.get("history")
    if not isinstance(history, dict):
        data["history"] = {}
    return data


def _save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _record_prompt_delivery(path: Path, prompt_date: str) -> None:
    state = _load_state(path)
    history = state.setdefault("history", {})
    entry = history.setdefault(prompt_date, {})
    entry["prompted_at"] = _utc_now()
    _trim_history(history)
    _save_state(path, state)


def _record_result(
    path: Path,
    prompt_date: str,
    *,
    status: str,
    action: str,
    details: dict[str, Any] | None = None,
) -> None:
    state = _load_state(path)
    history = state.setdefault("history", {})
    entry = history.setdefault(prompt_date, {})
    entry["status"] = status
    entry["action"] = action
    entry["updated_at"] = _utc_now()
    if details is not None:
        entry["details"] = details
    _trim_history(history)
    _save_state(path, state)


def _trim_history(history: dict[str, Any]) -> None:
    if len(history) <= _HISTORY_LIMIT:
        return
    for key in sorted(history)[:-_HISTORY_LIMIT]:
        history.pop(key, None)
