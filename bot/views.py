"""Tracking of message IDs that compose the user's current "view".

A view is a set of bot messages on screen that together form a logical
screen (e.g. the filters list, the blacklist, the main menu). When the
user navigates to a different view, the messages of the old one are
deleted.
"""
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from redis.asyncio import Redis

logger = logging.getLogger(__name__)


def _key(chat_id: int) -> str:
    return f"view:{chat_id}"


class ViewMessages:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def get(self, chat_id: int) -> list[int]:
        raw = await self._redis.lrange(_key(chat_id), 0, -1)
        return [int(item) for item in raw]

    async def set(self, chat_id: int, message_ids: list[int]) -> None:
        key = _key(chat_id)
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.delete(key)
            if message_ids:
                pipe.rpush(key, *message_ids)
            await pipe.execute()

    async def add(self, chat_id: int, message_id: int) -> None:
        await self._redis.rpush(_key(chat_id), message_id)

    async def remove(self, chat_id: int, message_id: int) -> None:
        await self._redis.lrem(_key(chat_id), 1, message_id)

    async def clear(self, chat_id: int) -> None:
        await self._redis.delete(_key(chat_id))


async def delete_current_view(
    bot: Bot, chat_id: int, view_messages: ViewMessages
) -> None:
    """Delete all messages of the current view from the chat and clear Redis."""
    ids = await view_messages.get(chat_id)
    for msg_id in ids:
        try:
            await bot.delete_message(chat_id, msg_id)
        except TelegramBadRequest as exc:
            logger.debug(
                "delete_current_view: cannot delete %s in %s: %s",
                msg_id, chat_id, exc,
            )
    await view_messages.clear(chat_id)
