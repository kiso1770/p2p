"""Tests for the /start handler."""
import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import Message

from bot.handlers.start import handle_start
from bot.views import ViewMessages
from services.tracking.buffer import RedisOrderBuffer
from services.tracking.state import RedisTrackingStateRepo, TrackingState

pytestmark = pytest.mark.integration


def _fake_user(telegram_id: int = 12345):
    user = MagicMock()
    user.telegram_id = telegram_id
    return user


def _fake_message(chat_id: int = 12345):
    msg = MagicMock(spec=Message)
    msg.chat = MagicMock(id=chat_id)
    sent = MagicMock(message_id=999)
    msg.answer = AsyncMock(return_value=sent)
    return msg


def _fake_bot():
    bot = MagicMock()
    bot.delete_message = AsyncMock()
    return bot


async def test_start_for_new_user_sends_welcome(redis_client):
    state_repo = RedisTrackingStateRepo(redis_client)
    buffer = RedisOrderBuffer(redis_client)
    view_messages = ViewMessages(redis_client)
    msg = _fake_message()

    await handle_start(
        message=msg,
        user=_fake_user(),
        is_new_user=True,
        bot=_fake_bot(),
        state_repo=state_repo,
        buffer=buffer,
        view_messages=view_messages,
    )

    msg.answer.assert_awaited_once()
    text = msg.answer.await_args.args[0]
    assert "Добро пожаловать" in text


async def test_start_for_returning_user_sends_welcome_back(redis_client):
    state_repo = RedisTrackingStateRepo(redis_client)
    buffer = RedisOrderBuffer(redis_client)
    view_messages = ViewMessages(redis_client)
    msg = _fake_message()

    await handle_start(
        message=msg,
        user=_fake_user(),
        is_new_user=False,
        bot=_fake_bot(),
        state_repo=state_repo,
        buffer=buffer,
        view_messages=view_messages,
    )

    text = msg.answer.await_args.args[0]
    assert "С возвращением" in text


async def test_start_includes_main_menu_keyboard(redis_client):
    state_repo = RedisTrackingStateRepo(redis_client)
    buffer = RedisOrderBuffer(redis_client)
    view_messages = ViewMessages(redis_client)
    msg = _fake_message()

    await handle_start(
        message=msg,
        user=_fake_user(),
        is_new_user=True,
        bot=_fake_bot(),
        state_repo=state_repo,
        buffer=buffer,
        view_messages=view_messages,
    )

    kwargs = msg.answer.await_args.kwargs
    kb = kwargs["reply_markup"]
    callbacks = {btn.callback_data for row in kb.inline_keyboard for btn in row}
    assert callbacks == {"menu:filters", "menu:settings"}


async def test_start_stops_active_tracking(redis_client, sample_ads):
    state_repo = RedisTrackingStateRepo(redis_client)
    buffer = RedisOrderBuffer(redis_client)

    chat_id = 99999
    await state_repo.set(
        chat_id,
        TrackingState(
            filter_id=1,
            header_message_id=10,
            order_message_ids=[11, 12, 13],
            last_activity_at=time.time(),
        ),
    )
    await buffer.set(chat_id, sample_ads)

    bot = _fake_bot()
    msg = _fake_message(chat_id=chat_id)
    view_messages = ViewMessages(redis_client)

    await handle_start(
        message=msg,
        user=_fake_user(),
        is_new_user=False,
        bot=bot,
        state_repo=state_repo,
        buffer=buffer,
        view_messages=view_messages,
    )

    # Tracking state must be cleared
    assert await state_repo.get(chat_id) is None
    assert await buffer.length(chat_id) == 0

    # Bot called to delete header + 3 order messages
    assert bot.delete_message.await_count == 4
