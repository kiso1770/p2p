"""Tests for settings + blacklist handlers (Phase 8)."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.handlers.settings import (
    back_to_main,
    blacklist_back_to_settings,
    cancel_clear,
    clear_all_prompt,
    confirm_clear,
    delete_blacklist_entry,
    show_blacklist,
    show_settings,
)
from bot.views import ViewMessages
from db.repositories import BlacklistRepo, UserRepo

pytestmark = pytest.mark.integration


def _fake_callback(data: str, chat_id: int = 100, message_id: int = 1):
    cb = MagicMock()
    cb.data = data
    cb.message = MagicMock()
    cb.message.chat = MagicMock(id=chat_id)
    cb.message.message_id = message_id
    cb.message.edit_text = AsyncMock()
    cb.message.delete = AsyncMock()
    cb.answer = AsyncMock()
    return cb


def _fake_bot(start_id: int = 200):
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


# ─── Settings menu ───────────────────────────────────────────────────


async def test_show_settings_sends_menu(redis_client):
    vm = ViewMessages(redis_client)
    bot = _fake_bot()
    cb = _fake_callback("menu:settings", chat_id=100)

    await show_settings(cb, bot, vm)

    bot.send_message.assert_awaited_once()
    text = bot.send_message.await_args.args[1]
    assert "Настройки" in text
    assert len(await vm.get(100)) == 1


async def test_back_to_main_clears_view(redis_client):
    vm = ViewMessages(redis_client)
    await vm.set(100, [10, 20])
    bot = _fake_bot()
    cb = _fake_callback("settings:back_to_main", chat_id=100)

    await back_to_main(cb, bot, vm)

    assert bot.delete_message.await_count == 2
    bot.send_message.assert_awaited_once()
    assert len(await vm.get(100)) == 1


# ─── Blacklist list ──────────────────────────────────────────────────


async def test_show_blacklist_empty(db_session, redis_client):
    user = await _make_user(db_session)
    vm = ViewMessages(redis_client)
    bot = _fake_bot()
    cb = _fake_callback("settings:blacklist", chat_id=user.telegram_id)

    await show_blacklist(cb, bot, user, db_session, vm)

    bot.send_message.assert_awaited_once()
    text = bot.send_message.await_args.args[1]
    assert "пуст" in text.lower()
    assert len(await vm.get(user.telegram_id)) == 1


async def test_show_blacklist_with_entries(db_session, redis_client):
    user = await _make_user(db_session)
    repo = BlacklistRepo(db_session)
    await repo.add(user.id, "Только VIP клиенты")
    await repo.add(user.id, "Скам не предлагать")
    await repo.add(user.id, "Курс не торгуется")
    await db_session.commit()

    vm = ViewMessages(redis_client)
    bot = _fake_bot()
    cb = _fake_callback("settings:blacklist", chat_id=user.telegram_id)

    await show_blacklist(cb, bot, user, db_session, vm)

    # 3 entries + 1 summary
    assert bot.send_message.await_count == 4
    ids = await vm.get(user.telegram_id)
    assert len(ids) == 4


async def test_blacklist_back_to_settings(redis_client):
    vm = ViewMessages(redis_client)
    await vm.set(100, [50, 60, 70])
    bot = _fake_bot()
    cb = _fake_callback("bl:back_to_settings", chat_id=100)

    await blacklist_back_to_settings(cb, bot, vm)

    assert bot.delete_message.await_count == 3
    bot.send_message.assert_awaited_once()


# ─── Delete one entry ────────────────────────────────────────────────


async def test_delete_entry_removes_from_db_and_chat(db_session, redis_client):
    user = await _make_user(db_session)
    entry = await BlacklistRepo(db_session).add(user.id, "test")
    await db_session.commit()

    vm = ViewMessages(redis_client)
    await vm.set(user.telegram_id, [42, 43])
    bot = _fake_bot()
    cb = _fake_callback(f"bl:delete:{entry.id}",
                        chat_id=user.telegram_id, message_id=42)

    await delete_blacklist_entry(cb, bot, user, db_session, vm)
    await db_session.commit()

    assert await BlacklistRepo(db_session).get_all_by_user(user.id) == []
    bot.delete_message.assert_awaited_once_with(user.telegram_id, 42)
    assert 42 not in await vm.get(user.telegram_id)


async def test_delete_entry_owner_check(db_session, redis_client):
    user_a = await _make_user(db_session, telegram_id=1)
    user_b = await _make_user(db_session, telegram_id=2)
    entry = await BlacklistRepo(db_session).add(user_a.id, "secret")
    await db_session.commit()

    vm = ViewMessages(redis_client)
    bot = _fake_bot()
    cb = _fake_callback(f"bl:delete:{entry.id}", chat_id=user_b.telegram_id)

    await delete_blacklist_entry(cb, bot, user_b, db_session, vm)
    await db_session.commit()

    # User A's entry survives
    remaining = await BlacklistRepo(db_session).get_all_by_user(user_a.id)
    assert len(remaining) == 1


# ─── Clear all flow ──────────────────────────────────────────────────


async def test_clear_all_prompt_edits_message():
    cb = _fake_callback("bl:clear_all")
    await clear_all_prompt(cb)
    cb.message.edit_text.assert_awaited_once()
    text = cb.message.edit_text.await_args.args[0]
    assert "Удалить все записи" in text


async def test_cancel_clear_restores_summary():
    cb = _fake_callback("bl:cancel_clear")
    await cancel_clear(cb)
    cb.message.edit_text.assert_awaited_once()


async def test_confirm_clear_deletes_all(db_session, redis_client):
    user = await _make_user(db_session)
    repo = BlacklistRepo(db_session)
    for text in ("a", "b", "c"):
        await repo.add(user.id, text)
    await db_session.commit()

    vm = ViewMessages(redis_client)
    await vm.set(user.telegram_id, [10, 20, 30, 40])
    bot = _fake_bot()
    cb = _fake_callback("bl:confirm_clear", chat_id=user.telegram_id)

    await confirm_clear(cb, bot, user, db_session, vm)
    await db_session.commit()

    assert await repo.get_all_by_user(user.id) == []
    # Old view messages were deleted, new (empty-state) view sent
    assert bot.delete_message.await_count == 4
    bot.send_message.assert_awaited()
    new_ids = await vm.get(user.telegram_id)
    assert len(new_ids) == 1
