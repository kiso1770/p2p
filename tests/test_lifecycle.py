"""Tests for services.tracking.lifecycle.stop_tracking."""
import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.exceptions import TelegramBadRequest

from services.tracking.buffer import RedisOrderBuffer
from services.tracking.lifecycle import stop_tracking
from services.tracking.state import RedisTrackingStateRepo, TrackingState

pytestmark = pytest.mark.integration


def _make_bot():
    bot = MagicMock()
    bot.delete_message = AsyncMock()
    return bot


async def test_stop_tracking_deletes_messages_and_clears_redis(redis_client, sample_ads):
    state_repo = RedisTrackingStateRepo(redis_client)
    buffer = RedisOrderBuffer(redis_client)

    state = TrackingState(
        filter_id=1,
        header_message_id=100,
        order_message_ids=[101, 102, 103],
        last_activity_at=time.time(),
    )
    await state_repo.set(7777, state)
    await buffer.set(7777, sample_ads)

    bot = _make_bot()
    result = await stop_tracking(bot, 7777, state_repo, buffer)

    assert result is True
    assert bot.delete_message.await_count == 4  # 3 orders + 1 header

    deleted_ids = [call.args[1] for call in bot.delete_message.await_args_list]
    assert set(deleted_ids) == {100, 101, 102, 103}

    assert await state_repo.get(7777) is None
    assert await buffer.length(7777) == 0


async def test_stop_tracking_no_active_session(redis_client):
    state_repo = RedisTrackingStateRepo(redis_client)
    buffer = RedisOrderBuffer(redis_client)
    bot = _make_bot()

    result = await stop_tracking(bot, 555, state_repo, buffer)
    assert result is False
    bot.delete_message.assert_not_called()


async def test_stop_tracking_swallows_telegram_errors(redis_client):
    state_repo = RedisTrackingStateRepo(redis_client)
    buffer = RedisOrderBuffer(redis_client)

    state = TrackingState(
        filter_id=1,
        header_message_id=100,
        order_message_ids=[101, 102],
        last_activity_at=time.time(),
    )
    await state_repo.set(8888, state)

    bot = _make_bot()
    bot.delete_message = AsyncMock(
        side_effect=TelegramBadRequest(method=MagicMock(), message="message not found")
    )

    # Should not raise
    result = await stop_tracking(bot, 8888, state_repo, buffer)
    assert result is True
    assert await state_repo.get(8888) is None
