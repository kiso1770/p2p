"""Tests for bot.views (ViewMessages + delete_current_view)."""
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.exceptions import TelegramBadRequest

from bot.views import ViewMessages, delete_current_view

pytestmark = pytest.mark.integration


async def test_set_and_get(redis_client):
    vm = ViewMessages(redis_client)
    await vm.set(123, [10, 20, 30])
    assert await vm.get(123) == [10, 20, 30]


async def test_set_replaces(redis_client):
    vm = ViewMessages(redis_client)
    await vm.set(1, [1, 2, 3])
    await vm.set(1, [4, 5])
    assert await vm.get(1) == [4, 5]


async def test_get_empty(redis_client):
    vm = ViewMessages(redis_client)
    assert await vm.get(99) == []


async def test_add_and_remove(redis_client):
    vm = ViewMessages(redis_client)
    await vm.set(1, [10, 20])
    await vm.add(1, 30)
    assert await vm.get(1) == [10, 20, 30]
    await vm.remove(1, 20)
    assert await vm.get(1) == [10, 30]


async def test_clear(redis_client):
    vm = ViewMessages(redis_client)
    await vm.set(1, [10, 20])
    await vm.clear(1)
    assert await vm.get(1) == []


async def test_delete_current_view_deletes_messages_and_clears(redis_client):
    vm = ViewMessages(redis_client)
    await vm.set(1, [100, 200, 300])

    bot = MagicMock()
    bot.delete_message = AsyncMock()

    await delete_current_view(bot, 1, vm)

    assert bot.delete_message.await_count == 3
    deleted_ids = [c.args[1] for c in bot.delete_message.await_args_list]
    assert sorted(deleted_ids) == [100, 200, 300]
    assert await vm.get(1) == []


async def test_delete_current_view_no_messages(redis_client):
    vm = ViewMessages(redis_client)
    bot = MagicMock()
    bot.delete_message = AsyncMock()

    await delete_current_view(bot, 1, vm)

    bot.delete_message.assert_not_called()


async def test_delete_current_view_swallows_telegram_errors(redis_client):
    vm = ViewMessages(redis_client)
    await vm.set(1, [100, 200])

    bot = MagicMock()
    bot.delete_message = AsyncMock(
        side_effect=TelegramBadRequest(method=MagicMock(), message="not found")
    )

    # Must not raise
    await delete_current_view(bot, 1, vm)
    assert await vm.get(1) == []
