"""Tests for filter list/delete handlers (Phase 5a)."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.handlers.filters import (
    back_to_main_menu,
    cancel_delete,
    confirm_delete,
    do_delete,
    show_filters,
)
from bot.views import ViewMessages
from db.repositories import FilterRepo, UserRepo

pytestmark = pytest.mark.integration


def _fake_callback(data: str, chat_id: int = 100, message_id: int = 1):
    callback = MagicMock()
    callback.data = data
    callback.message = MagicMock()
    callback.message.chat = MagicMock(id=chat_id)
    callback.message.message_id = message_id
    callback.message.edit_text = AsyncMock()
    callback.message.delete = AsyncMock()
    callback.answer = AsyncMock()
    return callback


def _fake_bot(start_id: int = 100):
    """Bot whose send_message returns sequential message IDs."""
    bot = MagicMock()
    counter = {"i": start_id}

    async def send(chat_id, text, **kwargs):
        counter["i"] += 1
        return MagicMock(message_id=counter["i"])

    bot.send_message = AsyncMock(side_effect=send)
    bot.delete_message = AsyncMock()
    return bot


async def _make_user(db_session, telegram_id: int = 1):
    user = await UserRepo(db_session).get_or_create(telegram_id, username=None)
    await db_session.commit()
    return user


# ─── show_filters ────────────────────────────────────────────────────


async def test_show_filters_empty(db_session, redis_client):
    user = await _make_user(db_session)
    vm = ViewMessages(redis_client)
    bot = _fake_bot()
    cb = _fake_callback("menu:filters", chat_id=user.telegram_id)

    await show_filters(cb, bot, user, db_session, vm)

    bot.send_message.assert_awaited_once()
    text = bot.send_message.await_args.args[1]
    assert "У вас пока нет фильтров" in text

    ids = await vm.get(user.telegram_id)
    assert len(ids) == 1


async def test_show_filters_with_filters(db_session, redis_client):
    user = await _make_user(db_session)
    fr = FilterRepo(db_session)
    await fr.create(user.id, name="A", currency_id="RUB", side=0)
    await fr.create(user.id, name="B", currency_id="USD", side=1)
    await fr.create(user.id, name="C", currency_id="EUR", side=0)
    await db_session.commit()

    vm = ViewMessages(redis_client)
    bot = _fake_bot()
    cb = _fake_callback("menu:filters", chat_id=user.telegram_id)

    await show_filters(cb, bot, user, db_session, vm)

    # 3 filters + 1 summary = 4 messages
    assert bot.send_message.await_count == 4
    ids = await vm.get(user.telegram_id)
    assert len(ids) == 4


async def test_show_filters_clears_old_view(db_session, redis_client):
    user = await _make_user(db_session)
    vm = ViewMessages(redis_client)
    await vm.set(user.telegram_id, [555, 666])

    bot = _fake_bot()
    cb = _fake_callback("menu:filters", chat_id=user.telegram_id)

    await show_filters(cb, bot, user, db_session, vm)

    # Two stale messages should have been deleted
    assert bot.delete_message.await_count == 2


# ─── back_to_main_menu ───────────────────────────────────────────────


async def test_back_to_main_menu_clears_and_sends_new(redis_client):
    vm = ViewMessages(redis_client)
    await vm.set(100, [10, 20, 30])

    bot = _fake_bot()
    cb = _fake_callback("menu:back_to_main", chat_id=100)

    await back_to_main_menu(cb, bot, vm)

    assert bot.delete_message.await_count == 3
    bot.send_message.assert_awaited_once()
    ids = await vm.get(100)
    assert len(ids) == 1


# ─── delete flow ─────────────────────────────────────────────────────


async def test_confirm_delete_shows_confirmation(db_session, redis_client):
    user = await _make_user(db_session)
    flt = await FilterRepo(db_session).create(user.id, "X", "RUB", 0)
    await db_session.commit()

    cb = _fake_callback(f"filter:delete:{flt.id}", chat_id=user.telegram_id)
    await confirm_delete(cb, user, db_session)

    cb.message.edit_text.assert_awaited_once()
    text = cb.message.edit_text.await_args.args[0]
    assert "Удалить" in text


async def test_do_delete_removes_filter(db_session, redis_client):
    user = await _make_user(db_session)
    flt = await FilterRepo(db_session).create(user.id, "X", "RUB", 0)
    await db_session.commit()

    vm = ViewMessages(redis_client)
    await vm.set(user.telegram_id, [42])

    bot = _fake_bot()
    cb = _fake_callback(f"filter:confirm_delete:{flt.id}",
                        chat_id=user.telegram_id, message_id=42)
    await do_delete(cb, bot, user, db_session, vm)
    await db_session.commit()

    assert await FilterRepo(db_session).get_by_id(flt.id, user.id) is None
    bot.delete_message.assert_awaited_once_with(user.telegram_id, 42)
    assert await vm.get(user.telegram_id) == []


async def test_do_delete_owner_check(db_session, redis_client):
    user_a = await _make_user(db_session, telegram_id=1)
    user_b = await _make_user(db_session, telegram_id=2)
    flt = await FilterRepo(db_session).create(user_a.id, "X", "RUB", 0)
    await db_session.commit()

    vm = ViewMessages(redis_client)
    bot = _fake_bot()
    cb = _fake_callback(f"filter:confirm_delete:{flt.id}", chat_id=user_b.telegram_id)
    await do_delete(cb, bot, user_b, db_session, vm)
    await db_session.commit()

    # User A's filter is still there
    assert await FilterRepo(db_session).get_by_id(flt.id, user_a.id) is not None


async def test_cancel_delete_restores_filter_view(db_session):
    user = await _make_user(db_session)
    flt = await FilterRepo(db_session).create(user.id, "X", "RUB", 0)
    await db_session.commit()

    cb = _fake_callback(f"filter:cancel_delete:{flt.id}", chat_id=user.telegram_id)
    await cancel_delete(cb, user, db_session)

    cb.message.edit_text.assert_awaited_once()
    text = cb.message.edit_text.await_args.args[0]
    assert "X" in text  # filter name in restored view
