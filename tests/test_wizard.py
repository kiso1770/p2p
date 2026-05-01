"""Tests for the filter creation wizard (Phase 5b)."""
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from bot.handlers.wizard import (
    back_to_currency,
    back_to_side,
    cancel_wizard,
    chose_currency,
    chose_side,
    receive_name,
    start_wizard,
)
from bot.states.wizard import CreateFilter
from bot.views import ViewMessages
from db.repositories import FilterRepo, UserRepo

pytestmark = pytest.mark.integration


def _fake_callback(data: str, chat_id: int = 100, message_id: int = 1):
    cb = MagicMock()
    cb.data = data
    cb.message = MagicMock()
    cb.message.chat = MagicMock(id=chat_id)
    cb.message.message_id = message_id
    cb.message.edit_text = AsyncMock()
    cb.answer = AsyncMock()
    return cb


def _fake_message(text: str, chat_id: int = 100, message_id: int = 50):
    msg = MagicMock()
    msg.text = text
    msg.chat = MagicMock(id=chat_id)
    msg.message_id = message_id
    return msg


def _fake_bot(start_id: int = 100):
    bot = MagicMock()
    counter = {"i": start_id}

    async def send(chat_id, text, **kwargs):
        counter["i"] += 1
        return MagicMock(message_id=counter["i"])

    bot.send_message = AsyncMock(side_effect=send)
    bot.delete_message = AsyncMock()
    bot.edit_message_text = AsyncMock()
    return bot


def _state_for(chat_id: int) -> FSMContext:
    return FSMContext(
        storage=MemoryStorage(),
        key=StorageKey(bot_id=1, user_id=chat_id, chat_id=chat_id),
    )


async def _make_user(db_session, telegram_id: int = 1):
    user = await UserRepo(db_session).get_or_create(telegram_id, username=None)
    await db_session.commit()
    return user


# ─── Step transitions ────────────────────────────────────────────────


async def test_start_wizard_sets_state_and_sends_step_1(redis_client):
    vm = ViewMessages(redis_client)
    bot = _fake_bot()
    state = _state_for(100)
    cb = _fake_callback("filter:create", chat_id=100)

    await start_wizard(cb, bot, vm, state)

    bot.send_message.assert_awaited_once()
    text = bot.send_message.await_args.args[1]
    assert "шаг 1" in text.lower()
    assert await state.get_state() == CreateFilter.choosing_currency.state


async def test_chose_currency_advances_to_step_2():
    state = _state_for(100)
    await state.set_state(CreateFilter.choosing_currency)
    cb = _fake_callback("wiz:cur:RUB")

    await chose_currency(cb, state)

    data = await state.get_data()
    assert data["currency_id"] == "RUB"
    assert await state.get_state() == CreateFilter.choosing_side.state
    cb.message.edit_text.assert_awaited_once()


async def test_chose_currency_rejects_unknown_code():
    state = _state_for(100)
    await state.set_state(CreateFilter.choosing_currency)
    cb = _fake_callback("wiz:cur:XYZ")

    await chose_currency(cb, state)

    assert await state.get_state() == CreateFilter.choosing_currency.state
    cb.answer.assert_awaited_once()


async def test_chose_side_advances_to_step_3():
    state = _state_for(100)
    await state.set_state(CreateFilter.choosing_side)
    await state.update_data(currency_id="RUB")
    cb = _fake_callback("wiz:side:0")

    await chose_side(cb, state)

    data = await state.get_data()
    assert data["side"] == 0
    assert await state.get_state() == CreateFilter.entering_name.state


async def test_back_from_side_to_currency():
    state = _state_for(100)
    await state.set_state(CreateFilter.choosing_side)
    cb = _fake_callback("wiz:back")

    await back_to_currency(cb, state)

    assert await state.get_state() == CreateFilter.choosing_currency.state


async def test_back_from_name_to_side():
    state = _state_for(100)
    await state.set_state(CreateFilter.entering_name)
    await state.update_data(currency_id="RUB", side=0)
    cb = _fake_callback("wiz:back")

    await back_to_side(cb, state)

    assert await state.get_state() == CreateFilter.choosing_side.state


# ─── Cancel ──────────────────────────────────────────────────────────


async def test_cancel_clears_state_and_renders_filters(db_session, redis_client):
    user = await _make_user(db_session)
    vm = ViewMessages(redis_client)
    state = _state_for(user.telegram_id)
    await state.set_state(CreateFilter.entering_name)
    bot = _fake_bot()
    cb = _fake_callback("wiz:cancel", chat_id=user.telegram_id)

    await cancel_wizard(cb, bot, user, db_session, vm, state)

    assert await state.get_state() is None
    bot.send_message.assert_awaited()  # filter list rendered


# ─── Final step: name input ──────────────────────────────────────────


async def test_receive_valid_name_creates_filter(db_session, redis_client):
    user = await _make_user(db_session)
    vm = ViewMessages(redis_client)
    await vm.set(user.telegram_id, [501])

    state = _state_for(user.telegram_id)
    await state.set_state(CreateFilter.entering_name)
    await state.update_data(currency_id="RUB", side=0)

    bot = _fake_bot()
    msg = _fake_message("Утренний", chat_id=user.telegram_id)

    await receive_name(msg, bot, user, db_session, vm, state)
    await db_session.commit()

    filters = await FilterRepo(db_session).get_all_by_user(user.id)
    assert len(filters) == 1
    assert filters[0].name == "Утренний"
    assert filters[0].currency_id == "RUB"
    assert filters[0].side == 0
    # After successful creation we redirect into the params editor
    from bot.states.wizard import EditFilter
    assert await state.get_state() == EditFilter.main.state


async def test_receive_empty_name_shows_error(db_session, redis_client):
    user = await _make_user(db_session)
    vm = ViewMessages(redis_client)
    await vm.set(user.telegram_id, [501])

    state = _state_for(user.telegram_id)
    await state.set_state(CreateFilter.entering_name)
    await state.update_data(currency_id="RUB", side=0)

    bot = _fake_bot()
    msg = _fake_message("   ", chat_id=user.telegram_id)

    await receive_name(msg, bot, user, db_session, vm, state)

    bot.edit_message_text.assert_awaited_once()
    text = bot.edit_message_text.await_args.args[0]
    assert "пустым" in text
    # State unchanged
    assert await state.get_state() == CreateFilter.entering_name.state
    # No filter created
    assert await FilterRepo(db_session).get_all_by_user(user.id) == []


async def test_receive_too_long_name_shows_error(db_session, redis_client):
    user = await _make_user(db_session)
    vm = ViewMessages(redis_client)
    await vm.set(user.telegram_id, [501])

    state = _state_for(user.telegram_id)
    await state.set_state(CreateFilter.entering_name)
    await state.update_data(currency_id="RUB", side=0)

    bot = _fake_bot()
    msg = _fake_message("a" * 33, chat_id=user.telegram_id)

    await receive_name(msg, bot, user, db_session, vm, state)

    bot.edit_message_text.assert_awaited_once()
    assert "32 символа" in bot.edit_message_text.await_args.args[0]


async def test_receive_duplicate_name_shows_error(db_session, redis_client):
    user = await _make_user(db_session)
    await FilterRepo(db_session).create(user.id, "Дубль", "RUB", 0)
    await db_session.commit()

    vm = ViewMessages(redis_client)
    await vm.set(user.telegram_id, [501])

    state = _state_for(user.telegram_id)
    await state.set_state(CreateFilter.entering_name)
    await state.update_data(currency_id="RUB", side=0)

    bot = _fake_bot()
    msg = _fake_message("Дубль", chat_id=user.telegram_id)

    await receive_name(msg, bot, user, db_session, vm, state)

    bot.edit_message_text.assert_awaited_once()
    text = bot.edit_message_text.await_args.args[0]
    assert "уже существует" in text
    # Still only one filter
    assert len(await FilterRepo(db_session).get_all_by_user(user.id)) == 1
