"""Transport-agnostic notification delivery protocol."""

from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class NotificationService(Protocol):
    """Transport-agnostic notification delivery.

    Implemented by both TelegramNotificationService and
    MatrixNotificationService so the supervisor and bus can send
    notifications without knowing which transport is active.
    """

    async def notify(self, chat_id: int, text: str) -> None:
        """Send a notification to a specific chat/room."""
        ...

    async def notify_all(self, text: str) -> None:
        """Send a notification to all authorized users/rooms."""
        ...


class CompositeNotificationService:
    """Fans out notifications to multiple transport-specific services."""

    def __init__(self) -> None:
        self._services: list[NotificationService] = []

    def add(self, service: NotificationService) -> None:
        self._services.append(service)

    def remove(self, service: NotificationService) -> None:
        self._services = [existing for existing in self._services if existing is not service]

    def replace(self, old: NotificationService, new: NotificationService) -> None:
        for index, existing in enumerate(self._services):
            if existing is old:
                self._services[index] = new
                return
        self._services.append(new)

    async def notify(self, chat_id: int, text: str) -> None:
        for svc in self._services:
            try:
                await svc.notify(chat_id, text)
            except Exception:  # noqa: BLE001
                logger.exception("Notification delivery failed for chat_id=%s", chat_id)

    async def notify_all(self, text: str) -> None:
        for svc in self._services:
            try:
                await svc.notify_all(text)
            except Exception:  # noqa: BLE001
                logger.exception("Broadcast notification delivery failed")
