import logging

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest

from services.tracking.buffer import RedisOrderBuffer
from services.tracking.state import RedisTrackingStateRepo

logger = logging.getLogger(__name__)


async def stop_tracking(
    bot: Bot,
    chat_id: int,
    state_repo: RedisTrackingStateRepo,
    buffer: RedisOrderBuffer,
) -> bool:
    """Best-effort cleanup of an active tracking session.

    Removes header/order messages from the chat and clears the Redis state +
    buffer. Returns True if there was an active session, False otherwise.

    NOTE: in Phase 6 this will also cancel the polling asyncio task.
    """
    state = await state_repo.get(chat_id)
    if state is None:
        return False

    message_ids = list(state.order_message_ids) + [state.header_message_id]
    for msg_id in message_ids:
        try:
            await bot.delete_message(chat_id, msg_id)
        except TelegramBadRequest as exc:
            logger.debug(
                "stop_tracking: cannot delete message %s in chat %s: %s",
                msg_id, chat_id, exc,
            )

    await state_repo.delete(chat_id)
    await buffer.clear(chat_id)
    return True
