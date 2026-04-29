"""MultiBotAdapter: wraps multiple transport bots behind a single BotProtocol."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TYPE_CHECKING

from ductor_bot.bus.bus import MessageBus
from ductor_bot.bus.lock_pool import LockPool
from ductor_bot.infra.restart import EXIT_RESTART
from ductor_bot.messenger.notifications import CompositeNotificationService

if TYPE_CHECKING:
    from ductor_bot.config import AgentConfig
    from ductor_bot.messenger.notifications import NotificationService
    from ductor_bot.messenger.protocol import BotProtocol
    from ductor_bot.multiagent.bus import AsyncInterAgentResult
    from ductor_bot.orchestrator.core import Orchestrator
    from ductor_bot.tasks.models import TaskResult
    from ductor_bot.workspace.paths import DuctorPaths

logger = logging.getLogger(__name__)

_SECONDARY_RESTART_BASE_SECONDS = 1.0
_SECONDARY_RESTART_MAX_SECONDS = 10.0
_SECONDARY_RESTART_STABLE_SECONDS = 30.0
_SECONDARY_DEGRADED_NOTIFY_AFTER_ATTEMPTS = 3


class MultiBotAdapter:
    """Wraps multiple transport bots into a single BotProtocol facade.

    The **primary** bot (first transport) creates the orchestrator during
    startup.  Secondary bots receive the orchestrator before their ``run()``
    is called, so their startup skips orchestrator creation.

    All bots share a single ``MessageBus`` and ``LockPool``.
    """

    def __init__(
        self,
        config: AgentConfig,
        *,
        agent_name: str = "main",
    ) -> None:
        self._config = config
        self._agent_name = agent_name
        self._lock_pool = LockPool()
        self._bus = MessageBus(lock_pool=self._lock_pool)
        self._abort_all_callback: Callable[[], Awaitable[int]] | None = None
        self._restart_idle_checker: Callable[[], int] | None = None

        transports = config.transports
        if not transports:
            msg = "MultiBotAdapter requires at least one transport"
            raise ValueError(msg)

        self._transport_names = list(transports)
        self._primary_transport = self._transport_names[0]
        self._secondary_transport_names = self._transport_names[1:]
        self._secondary_restart_attempts = {
            transport: 0 for transport in self._secondary_transport_names
        }
        self._secondary_degraded_notified: set[str] = set()
        self._secondary_stabilizers: dict[str, asyncio.Task[None]] = {}

        self._primary: BotProtocol = self._create_bot(self._primary_transport)
        self._secondaries: dict[str, BotProtocol] = {
            transport: self._create_bot(transport) for transport in self._secondary_transport_names
        }

        self._notification_service = CompositeNotificationService()
        for bot in self._all_bots():
            self._notification_service.add(bot.notification_service)

    # -- BotProtocol: properties delegated to primary --------------------------

    @property
    def orchestrator(self) -> Orchestrator | None:
        return self._primary.orchestrator

    @property
    def config(self) -> AgentConfig:
        return self._config

    @property
    def notification_service(self) -> NotificationService:
        return self._notification_service

    # -- BotProtocol: methods delegated to primary -----------------------------

    def _create_bot(self, transport_name: str) -> BotProtocol:
        from ductor_bot.messenger.registry import _create_single_bot

        bot = _create_single_bot(
            transport_name,
            self._config,
            agent_name=self._agent_name,
            bus=self._bus,
            lock_pool=self._lock_pool,
        )
        if self._abort_all_callback is not None:
            bot.set_abort_all_callback(self._abort_all_callback)
        if self._restart_idle_checker is not None:
            bot.set_restart_idle_checker(self._restart_idle_checker)
        return bot

    def _all_bots(self) -> list[BotProtocol]:
        return [
            self._primary,
            *[
                self._secondaries[transport]
                for transport in self._secondary_transport_names
                if transport in self._secondaries
            ],
        ]

    def register_startup_hook(self, hook: Callable[[], Awaitable[None]]) -> None:
        self._primary.register_startup_hook(hook)

    def set_abort_all_callback(self, callback: Callable[[], Awaitable[int]]) -> None:
        self._abort_all_callback = callback
        for bot in self._all_bots():
            bot.set_abort_all_callback(callback)

    def set_restart_idle_checker(self, callback: Callable[[], int]) -> None:
        self._restart_idle_checker = callback
        for bot in self._all_bots():
            bot.set_restart_idle_checker(callback)

    # -- BotProtocol: methods that fan out to all bots -------------------------

    async def on_async_interagent_result(self, result: AsyncInterAgentResult) -> None:
        for bot in self._all_bots():
            await bot.on_async_interagent_result(result)

    async def on_task_result(self, result: TaskResult) -> None:
        for bot in self._all_bots():
            await bot.on_task_result(result)

    async def on_task_question(
        self,
        task_id: str,
        question: str,
        prompt_preview: str,
        chat_id: int,
        thread_id: int | None = None,
    ) -> None:
        for bot in self._all_bots():
            await bot.on_task_question(task_id, question, prompt_preview, chat_id, thread_id)

    def file_roots(self, paths: DuctorPaths) -> list[Path] | None:
        return self._primary.file_roots(paths)

    # -- BotProtocol: run / shutdown -------------------------------------------

    async def _cancel_tasks(self, tasks: list[asyncio.Task[object]]) -> None:
        pending = [task for task in tasks if not task.done()]
        if not pending:
            return
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)

    async def _cancel_secondary_stabilizers(self) -> None:
        await self._cancel_tasks(list(self._secondary_stabilizers.values()))
        self._secondary_stabilizers.clear()

    def _cancel_secondary_stabilizer(self, transport: str) -> None:
        task = self._secondary_stabilizers.pop(transport, None)
        if task is not None and not task.done():
            task.cancel()

    def _attach_shared_orchestrator(self, bot: BotProtocol) -> None:
        bot._orchestrator = self._primary.orchestrator  # type: ignore[attr-defined]
        bot._owns_orchestrator = False  # type: ignore[attr-defined]

    def _start_secondary_task(
        self, transport: str, bot: BotProtocol
    ) -> tuple[asyncio.Task[int], BotProtocol, float]:
        self._attach_shared_orchestrator(bot)
        task = asyncio.create_task(bot.run(), name=f"multi:secondary:{transport}")
        return task, bot, asyncio.get_running_loop().time()

    def _next_secondary_restart_delay(self, transport: str, *, runtime_seconds: float) -> tuple[int, float]:
        attempts = self._secondary_restart_attempts.get(transport, 0)
        if runtime_seconds >= _SECONDARY_RESTART_STABLE_SECONDS:
            attempts = 0
        attempts += 1
        self._secondary_restart_attempts[transport] = attempts
        delay = min(
            _SECONDARY_RESTART_BASE_SECONDS * (2 ** (attempts - 1)),
            _SECONDARY_RESTART_MAX_SECONDS,
        )
        return attempts, delay

    def _secondary_degraded_message(self, transport: str, *, attempt: int) -> str:
        return (
            f"Warning: secondary transport '{transport}' is unstable "
            f"({attempt} restart attempts). Primary transport "
            f"'{self._primary_transport}' remains active while local recovery continues."
        )

    def _secondary_unavailable_message(self, transport: str) -> str:
        return (
            f"Warning: secondary transport '{transport}' is unavailable after local restart failure. "
            f"Primary transport '{self._primary_transport}' remains active."
        )

    def _secondary_recovered_message(self, transport: str) -> str:
        return (
            f"Recovered: secondary transport '{transport}' has been stable for "
            f"{int(_SECONDARY_RESTART_STABLE_SECONDS)}s and is fully active again."
        )

    async def _notify_health_change(self, text: str) -> None:
        try:
            await self._notification_service.notify_all(text)
        except Exception:  # pragma: no cover - CompositeNotificationService already guards fanout
            logger.exception("Failed to send multi-transport health notification")

    async def _maybe_notify_secondary_degraded(self, transport: str, *, attempt: int) -> None:
        if attempt < _SECONDARY_DEGRADED_NOTIFY_AFTER_ATTEMPTS:
            return
        if transport in self._secondary_degraded_notified:
            return
        self._secondary_degraded_notified.add(transport)
        await self._notify_health_change(self._secondary_degraded_message(transport, attempt=attempt))

    async def _mark_secondary_unavailable(self, transport: str) -> None:
        if transport in self._secondary_degraded_notified:
            return
        self._secondary_degraded_notified.add(transport)
        await self._notify_health_change(self._secondary_unavailable_message(transport))

    def _schedule_secondary_stability_watch(self, transport: str, bot: BotProtocol) -> None:
        self._cancel_secondary_stabilizer(transport)

        async def _watch() -> None:
            try:
                await asyncio.sleep(_SECONDARY_RESTART_STABLE_SECONDS)
                if self._secondaries.get(transport) is not bot:
                    return
                self._secondary_restart_attempts[transport] = 0
                if transport in self._secondary_degraded_notified:
                    self._secondary_degraded_notified.remove(transport)
                    await self._notify_health_change(self._secondary_recovered_message(transport))
            except asyncio.CancelledError:
                return
            finally:
                current = self._secondary_stabilizers.get(transport)
                if current is task:
                    self._secondary_stabilizers.pop(transport, None)

        task = asyncio.create_task(_watch(), name=f"multi:secondary:{transport}:stability")
        self._secondary_stabilizers[transport] = task

    async def _retire_secondary_bot(self, transport: str, bot: BotProtocol) -> None:
        self._cancel_secondary_stabilizer(transport)
        current = self._secondaries.get(transport)
        if current is bot:
            self._secondaries.pop(transport, None)
        self._notification_service.remove(bot.notification_service)
        transport_adapter = getattr(bot, "_transport_adapter", None)
        if transport_adapter is not None:
            self._bus.unregister_transport(transport_adapter)
        try:
            await bot.shutdown()
        except Exception:  # noqa: BLE001
            logger.exception("Secondary transport '%s' cleanup failed", transport)

    async def _restart_secondary(
        self,
        transport: str,
        bot: BotProtocol,
        *,
        started_at: float,
        reason: str,
        primary_task: asyncio.Task[int],
    ) -> tuple[asyncio.Task[int], BotProtocol, float] | None:
        runtime_seconds = max(asyncio.get_running_loop().time() - started_at, 0.0)
        attempt, delay = self._next_secondary_restart_delay(
            transport,
            runtime_seconds=runtime_seconds,
        )
        await self._maybe_notify_secondary_degraded(transport, attempt=attempt)
        logger.warning(
            "Secondary transport '%s' %s; restarting locally in %.1fs (attempt %d)",
            transport,
            reason,
            delay,
            attempt,
        )
        await self._retire_secondary_bot(transport, bot)

        while True:
            done, _ = await asyncio.wait(
                {primary_task},
                timeout=delay,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if primary_task in done:
                return None

            try:
                new_bot = self._create_bot(transport)
            except Exception:  # noqa: BLE001
                logger.exception(
                    "Failed to recreate secondary transport '%s'; primary transport continues",
                    transport,
                )
                await self._mark_secondary_unavailable(transport)
                attempt, delay = self._next_secondary_restart_delay(
                    transport,
                    runtime_seconds=0.0,
                )
                logger.warning(
                    "Secondary transport '%s' recreate failed; retrying in %.1fs (attempt %d)",
                    transport,
                    delay,
                    attempt,
                )
                continue

            self._secondaries[transport] = new_bot
            self._notification_service.add(new_bot.notification_service)
            self._schedule_secondary_stability_watch(transport, new_bot)
            return self._start_secondary_task(transport, new_bot)

    async def run(self) -> int:
        """Start all bots: primary first, then secondaries after orchestrator is ready.

        Primary transport owns clean shutdown. Secondary transports can request
        coordinated exit only via a non-zero exit code (e.g. ``EXIT_RESTART``).
        Unexpected secondary termination is recovered locally with backoff.
        """
        orch_ready = asyncio.Event()

        async def _signal_ready() -> None:
            orch_ready.set()

        self._primary.register_startup_hook(_signal_ready)

        primary_task = asyncio.create_task(self._primary.run(), name="multi:primary")
        ready_task = asyncio.create_task(orch_ready.wait(), name="multi:primary:ready")

        done, _ = await asyncio.wait(
            {primary_task, ready_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        await self._cancel_tasks([ready_task])

        if primary_task in done:
            return primary_task.result()

        secondary_tasks: dict[asyncio.Task[int], tuple[str, BotProtocol, float]] = {
            task: (transport, bot, started_at)
            for transport, bot in self._secondaries.items()
            for task, _bot, started_at in [self._start_secondary_task(transport, bot)]
        }

        try:
            while True:
                monitored = {primary_task, *secondary_tasks}
                done, _ = await asyncio.wait(monitored, return_when=asyncio.FIRST_COMPLETED)

                secondary_exit_code: int | None = None
                unexpected_terminations: list[tuple[str, BotProtocol, float, str]] = []

                for task in list(done):
                    if task is primary_task:
                        continue

                    transport, bot, started_at = secondary_tasks.pop(task)
                    try:
                        code = task.result()
                    except asyncio.CancelledError:
                        unexpected_terminations.append(
                            (transport, bot, started_at, "was cancelled unexpectedly")
                        )
                        continue
                    except Exception:  # noqa: BLE001
                        logger.exception(
                            "Secondary transport '%s' crashed; scheduling local restart",
                            transport,
                        )
                        unexpected_terminations.append((transport, bot, started_at, "crashed"))
                        continue

                    if code == 0:
                        unexpected_terminations.append((transport, bot, started_at, "exited cleanly"))
                        continue

                    logger.warning(
                        "Secondary transport '%s' requested coordinated exit (code=%d)",
                        transport,
                        code,
                    )
                    if secondary_exit_code is None or code == EXIT_RESTART:
                        secondary_exit_code = code

                if secondary_exit_code is not None:
                    await self._cancel_tasks([primary_task, *secondary_tasks])
                    return secondary_exit_code

                if primary_task in done:
                    for transport, bot, _started_at, _reason in unexpected_terminations:
                        await self._retire_secondary_bot(transport, bot)
                    await self._cancel_tasks(list(secondary_tasks))
                    return primary_task.result()

                for transport, bot, started_at, reason in unexpected_terminations:
                    restarted = await self._restart_secondary(
                        transport,
                        bot,
                        started_at=started_at,
                        reason=reason,
                        primary_task=primary_task,
                    )
                    if primary_task.done():
                        await self._cancel_tasks(list(secondary_tasks))
                        return primary_task.result()
                    if restarted is None:
                        continue
                    task, new_bot, new_started_at = restarted
                    secondary_tasks[task] = (transport, new_bot, new_started_at)

                if not secondary_tasks:
                    return await primary_task
        finally:
            await self._cancel_secondary_stabilizers()

    async def shutdown(self) -> None:
        """Shut down all bots."""
        await self._cancel_secondary_stabilizers()
        for bot in self._all_bots():
            await bot.shutdown()
