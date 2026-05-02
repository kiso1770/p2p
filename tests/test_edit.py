"""Tests for filter parameters editor (Phase 5c)."""
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from bot.handlers.edit import (
    back_step,
    group_amount,
    group_description,
    group_experience,
    group_sort,
    input_count,
    input_rate,
    input_trades,
    open_editor,
    receive_amount_max,
    receive_amount_min,
    receive_blacklist,
    receive_count,
    receive_rate,
    receive_trades,
    receive_whitelist,
    set_sort_direction,
    skip_step,
    toggle_no_description,
)
from bot.states.wizard import EditFilter
from bot.views import ViewMessages
from db.repositories import FilterRepo, UserRepo

pytestmark = pytest.mark.integration


def _fake_callback(data: str, chat_id: int = 100, message_id: int = 500):
    cb = MagicMock()
    cb.data = data
    cb.message = MagicMock()
    cb.message.chat = MagicMock(id=chat_id)
    cb.message.message_id = message_id
    cb.answer = AsyncMock()
    return cb


def _fake_message(text: str, chat_id: int = 100, message_id: int = 50):
    msg = MagicMock()
    msg.text = text
    msg.chat = MagicMock(id=chat_id)
    msg.message_id = message_id
    return msg


def _fake_bot():
    bot = MagicMock()
    counter = {"i": 500}

    async def send(chat_id, text, **kwargs):
        counter["i"] += 1
        return MagicMock(message_id=counter["i"])

    bot.send_message = AsyncMock(side_effect=send)
    bot.edit_message_text = AsyncMock()
    bot.delete_message = AsyncMock()
    return bot


def _state_for(chat_id: int) -> FSMContext:
    return FSMContext(
        storage=MemoryStorage(),
        key=StorageKey(bot_id=1, user_id=chat_id, chat_id=chat_id),
    )


async def _setup(db_session, redis_client, telegram_id: int = 100):
    user = await UserRepo(db_session).get_or_create(telegram_id, username=None)
    flt = await FilterRepo(db_session).create(user.id, "Test", "RUB", 0)
    await db_session.commit()
    vm = ViewMessages(redis_client)
    state = _state_for(user.telegram_id)
    return user, flt, vm, state


# ─── Open / Done ─────────────────────────────────────────────────────


async def test_open_editor_sets_state_and_sends_message(db_session, redis_client):
    user, flt, vm, state = await _setup(db_session, redis_client)
    bot = _fake_bot()
    cb = _fake_callback(f"filter:edit:{flt.id}", chat_id=user.telegram_id)

    await open_editor(cb, bot, user, db_session, vm, state)

    assert await state.get_state() == EditFilter.main.state
    bot.send_message.assert_awaited_once()
    data = await state.get_data()
    assert data["filter_id"] == flt.id


async def test_open_editor_owner_check(db_session, redis_client):
    user_a = await UserRepo(db_session).get_or_create(1, None)
    user_b = await UserRepo(db_session).get_or_create(2, None)
    flt = await FilterRepo(db_session).create(user_a.id, "X", "RUB", 0)
    await db_session.commit()

    vm = ViewMessages(redis_client)
    state = _state_for(user_b.telegram_id)
    bot = _fake_bot()
    cb = _fake_callback(f"filter:edit:{flt.id}", chat_id=user_b.telegram_id)

    await open_editor(cb, bot, user_b, db_session, vm, state)

    assert await state.get_state() is None
    bot.send_message.assert_not_called()


# ─── Amount range ────────────────────────────────────────────────────


async def test_amount_range_full_flow(db_session, redis_client):
    user, flt, vm, state = await _setup(db_session, redis_client)
    bot = _fake_bot()
    await state.set_state(EditFilter.main)
    await state.update_data(filter_id=flt.id, msg_id=999)

    # Click amount group
    await group_amount(_fake_callback("edit:group:amount", chat_id=user.telegram_id),
                      bot, user, db_session, state)
    assert await state.get_state() == EditFilter.amount_min.state

    # Enter min
    await receive_amount_min(_fake_message("500", chat_id=user.telegram_id),
                             bot, user, db_session, state)
    assert await state.get_state() == EditFilter.amount_max.state

    # Enter max
    await receive_amount_max(_fake_message("50000", chat_id=user.telegram_id),
                             bot, user, db_session, state)
    await db_session.commit()
    assert await state.get_state() == EditFilter.main.state

    refreshed = await FilterRepo(db_session).get_by_id(flt.id, user.id)
    assert refreshed.min_amount == Decimal("500")
    assert refreshed.max_amount == Decimal("50000")


async def test_amount_min_invalid_input_keeps_state(db_session, redis_client):
    user, flt, vm, state = await _setup(db_session, redis_client)
    bot = _fake_bot()
    await state.set_state(EditFilter.amount_min)
    await state.update_data(filter_id=flt.id, msg_id=999)

    await receive_amount_min(_fake_message("not a number", chat_id=user.telegram_id),
                             bot, user, db_session, state)

    assert await state.get_state() == EditFilter.amount_min.state
    bot.edit_message_text.assert_awaited()
    error_text = bot.edit_message_text.await_args.args[0]
    assert "положительное число" in error_text


async def test_amount_max_less_than_min_rejected(db_session, redis_client):
    user, flt, vm, state = await _setup(db_session, redis_client)
    bot = _fake_bot()
    await state.set_state(EditFilter.amount_max)
    await state.update_data(filter_id=flt.id, msg_id=999, pending_min="1000")

    await receive_amount_max(_fake_message("500", chat_id=user.telegram_id),
                             bot, user, db_session, state)

    assert await state.get_state() == EditFilter.amount_max.state
    refreshed = await FilterRepo(db_session).get_by_id(flt.id, user.id)
    assert refreshed.min_amount is None  # not saved


# ─── Skip behavior ───────────────────────────────────────────────────


async def test_skip_amount_min_advances_to_max(db_session, redis_client):
    user, flt, vm, state = await _setup(db_session, redis_client)
    bot = _fake_bot()
    await state.set_state(EditFilter.amount_min)
    await state.update_data(filter_id=flt.id, msg_id=999)

    await skip_step(_fake_callback("edit:skip", chat_id=user.telegram_id),
                    bot, user, db_session, state)

    assert await state.get_state() == EditFilter.amount_max.state
    data = await state.get_data()
    assert data["pending_min"] is None


async def test_skip_amount_max_saves_min_only(db_session, redis_client):
    user, flt, vm, state = await _setup(db_session, redis_client)
    bot = _fake_bot()
    await state.set_state(EditFilter.amount_max)
    await state.update_data(filter_id=flt.id, msg_id=999, pending_min="500")

    await skip_step(_fake_callback("edit:skip", chat_id=user.telegram_id),
                    bot, user, db_session, state)
    await db_session.commit()

    refreshed = await FilterRepo(db_session).get_by_id(flt.id, user.id)
    assert refreshed.min_amount == Decimal("500")
    assert refreshed.max_amount is None
    assert await state.get_state() == EditFilter.main.state


async def test_skip_min_trades_clears_field(db_session, redis_client):
    user, flt, vm, state = await _setup(db_session, redis_client)
    flt.min_trades_count = 100
    await db_session.commit()

    bot = _fake_bot()
    await state.set_state(EditFilter.min_trades)
    await state.update_data(filter_id=flt.id, msg_id=999)

    await skip_step(_fake_callback("edit:skip", chat_id=user.telegram_id),
                    bot, user, db_session, state)
    await db_session.commit()

    refreshed = await FilterRepo(db_session).get_by_id(flt.id, user.id)
    assert refreshed.min_trades_count is None
    assert await state.get_state() == EditFilter.experience.state


# ─── Experience ──────────────────────────────────────────────────────


async def test_min_trades_saved(db_session, redis_client):
    user, flt, vm, state = await _setup(db_session, redis_client)
    bot = _fake_bot()
    await state.set_state(EditFilter.min_trades)
    await state.update_data(filter_id=flt.id, msg_id=999)

    await receive_trades(_fake_message("100", chat_id=user.telegram_id),
                         bot, user, db_session, state)
    await db_session.commit()

    refreshed = await FilterRepo(db_session).get_by_id(flt.id, user.id)
    assert refreshed.min_trades_count == 100
    assert await state.get_state() == EditFilter.experience.state


async def test_min_rate_saved(db_session, redis_client):
    user, flt, vm, state = await _setup(db_session, redis_client)
    bot = _fake_bot()
    await state.set_state(EditFilter.min_rate)
    await state.update_data(filter_id=flt.id, msg_id=999)

    await receive_rate(_fake_message("95.5", chat_id=user.telegram_id),
                       bot, user, db_session, state)
    await db_session.commit()

    refreshed = await FilterRepo(db_session).get_by_id(flt.id, user.id)
    assert refreshed.min_completion_rate == Decimal("95.5")


async def test_min_rate_out_of_range_rejected(db_session, redis_client):
    user, flt, vm, state = await _setup(db_session, redis_client)
    bot = _fake_bot()
    await state.set_state(EditFilter.min_rate)
    await state.update_data(filter_id=flt.id, msg_id=999)

    await receive_rate(_fake_message("150", chat_id=user.telegram_id),
                       bot, user, db_session, state)

    refreshed = await FilterRepo(db_session).get_by_id(flt.id, user.id)
    assert refreshed.min_completion_rate is None


# ─── Description ─────────────────────────────────────────────────────


async def test_toggle_description_flips(db_session, redis_client):
    user, flt, vm, state = await _setup(db_session, redis_client)
    initial = flt.show_no_description
    bot = _fake_bot()
    await state.set_state(EditFilter.description)
    await state.update_data(filter_id=flt.id, msg_id=999)

    await toggle_no_description(_fake_callback("edit:toggle:desc", chat_id=user.telegram_id),
                                bot, user, db_session, state)
    await db_session.commit()

    refreshed = await FilterRepo(db_session).get_by_id(flt.id, user.id)
    assert refreshed.show_no_description != initial


async def test_whitelist_csv_parsed(db_session, redis_client):
    user, flt, vm, state = await _setup(db_session, redis_client)
    bot = _fake_bot()
    await state.set_state(EditFilter.whitelist)
    await state.update_data(filter_id=flt.id, msg_id=999)

    await receive_whitelist(_fake_message("СБП, Тинькофф,Сбер", chat_id=user.telegram_id),
                            bot, user, db_session, state)
    await db_session.commit()

    refreshed = await FilterRepo(db_session).get_by_id(flt.id, user.id)
    assert refreshed.whitelist_words == ["СБП", "Тинькофф", "Сбер"]


async def test_blacklist_empty_clears(db_session, redis_client):
    user, flt, vm, state = await _setup(db_session, redis_client)
    flt.blacklist_words = ["a", "b"]
    await db_session.commit()

    bot = _fake_bot()
    await state.set_state(EditFilter.blacklist)
    await state.update_data(filter_id=flt.id, msg_id=999)

    await receive_blacklist(_fake_message(",,, ", chat_id=user.telegram_id),
                            bot, user, db_session, state)
    await db_session.commit()

    refreshed = await FilterRepo(db_session).get_by_id(flt.id, user.id)
    assert refreshed.blacklist_words is None


# ─── Sort & count ────────────────────────────────────────────────────


async def test_set_sort_direction_desc(db_session, redis_client):
    user, flt, vm, state = await _setup(db_session, redis_client)
    bot = _fake_bot()
    await state.set_state(EditFilter.sort)
    await state.update_data(filter_id=flt.id, msg_id=999)

    await set_sort_direction(_fake_callback("edit:sort:DESC", chat_id=user.telegram_id),
                             bot, user, db_session, state)
    await db_session.commit()

    refreshed = await FilterRepo(db_session).get_by_id(flt.id, user.id)
    assert refreshed.sort_direction == "DESC"


async def test_orders_count_valid(db_session, redis_client):
    user, flt, vm, state = await _setup(db_session, redis_client)
    bot = _fake_bot()
    await state.set_state(EditFilter.orders_count)
    await state.update_data(filter_id=flt.id, msg_id=999)

    await receive_count(_fake_message("3", chat_id=user.telegram_id),
                        bot, user, db_session, state)
    await db_session.commit()

    refreshed = await FilterRepo(db_session).get_by_id(flt.id, user.id)
    assert refreshed.orders_count == 3


async def test_orders_count_out_of_range(db_session, redis_client):
    user, flt, vm, state = await _setup(db_session, redis_client)
    bot = _fake_bot()
    await state.set_state(EditFilter.orders_count)
    await state.update_data(filter_id=flt.id, msg_id=999)

    await receive_count(_fake_message("10", chat_id=user.telegram_id),
                        bot, user, db_session, state)

    refreshed = await FilterRepo(db_session).get_by_id(flt.id, user.id)
    assert refreshed.orders_count == 5  # default unchanged


async def test_refresh_interval_valid(db_session, redis_client):
    from bot.handlers.edit import receive_interval

    user, flt, vm, state = await _setup(db_session, redis_client)
    bot = _fake_bot()
    await state.set_state(EditFilter.refresh_interval)
    await state.update_data(filter_id=flt.id, msg_id=999)

    await receive_interval(_fake_message("60", chat_id=user.telegram_id),
                           bot, user, db_session, state)
    await db_session.commit()

    refreshed = await FilterRepo(db_session).get_by_id(flt.id, user.id)
    assert refreshed.refresh_interval_seconds == 60
    assert await state.get_state() == EditFilter.sort.state


async def test_refresh_interval_out_of_range(db_session, redis_client):
    from bot.handlers.edit import receive_interval

    user, flt, vm, state = await _setup(db_session, redis_client)
    bot = _fake_bot()
    await state.set_state(EditFilter.refresh_interval)
    await state.update_data(filter_id=flt.id, msg_id=999)

    await receive_interval(_fake_message("3", chat_id=user.telegram_id),
                           bot, user, db_session, state)

    refreshed = await FilterRepo(db_session).get_by_id(flt.id, user.id)
    assert refreshed.refresh_interval_seconds == 15  # default unchanged
    assert await state.get_state() == EditFilter.refresh_interval.state


async def test_refresh_interval_too_high(db_session, redis_client):
    from bot.handlers.edit import receive_interval

    user, flt, vm, state = await _setup(db_session, redis_client)
    bot = _fake_bot()
    await state.set_state(EditFilter.refresh_interval)
    await state.update_data(filter_id=flt.id, msg_id=999)

    await receive_interval(_fake_message("700", chat_id=user.telegram_id),
                           bot, user, db_session, state)

    refreshed = await FilterRepo(db_session).get_by_id(flt.id, user.id)
    assert refreshed.refresh_interval_seconds == 15
