"""Global registry of active TrackingEngine instances."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from services.tracking.engine import TrackingEngine

logger = logging.getLogger(__name__)


class EngineRegistry:
    def __init__(self) -> None:
        self._engines: dict[int, "TrackingEngine"] = {}

    def register(self, chat_id: int, engine: "TrackingEngine") -> None:
        self._engines[chat_id] = engine

    def get(self, chat_id: int) -> "TrackingEngine | None":
        return self._engines.get(chat_id)

    def unregister(self, chat_id: int) -> None:
        self._engines.pop(chat_id, None)

    async def stop_for(self, chat_id: int) -> bool:
        engine = self._engines.get(chat_id)
        if engine is None:
            return False
        try:
            await engine.stop()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to stop engine for chat %s: %s", chat_id, exc)
        return True

    async def stop_all(self) -> None:
        for chat_id in list(self._engines.keys()):
            await self.stop_for(chat_id)
