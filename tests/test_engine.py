"""Tests for TrackingEngine (Phase 6a) — focused on rendering and refresh logic."""
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from bot.views import ViewMessages
from db.repositories import FilterRepo, UserRepo
from services.bybit_client import BybitTimeoutError
from services.bybit_models import AdsListResult
from services.tracking.buffer import RedisOrderBuffer
from services.tracking.engine import TrackingEngine
from services.tracking.registry import EngineRegistry
from services.tracking.state import RedisTrackingStateRepo
from services.tracking.url import build_order_url
from tests.conftest import TEST_DATABASE_URL

pytestmark = pytest.mark.integration


def _fake_bot(start_id: int = 1000):
    bot = MagicMock()
    counter = {"i": start_id}

    async def send(chat_id, text, **kwargs):
        counter["i"] += 1
        return MagicMock(message_id=counter["i"])

    bot.send_message = AsyncMock(side_effect=send)
    bot.edit_message_text = AsyncMock()
    bot.delete_message = AsyncMock()
    return bot


def _fake_bybit_client(ads):
    client = MagicMock()
    client.get_online_ads = AsyncMock(return_value=AdsListResult(count=len(ads), items=ads))
    return client


def _fake_bybit_client_error(exc):
    client = MagicMock()
    client.get_online_ads = AsyncMock(side_effect=exc)
    return client


async def _setup_user_and_filter(db_session, telegram_id: int = 100):
    user = await UserRepo(db_session).get_or_create(telegram_id, username=None)
    flt = await FilterRepo(db_session).create(user.id, "Тест", "RUB", 0)
    await db_session.commit()
    return user, flt


def _make_engine(bot, user, flt, redis_client, db_session, bybit_client):
    engine = create_async_engine(TEST_DATABASE_URL)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    return TrackingEngine(
        bot=bot,
        chat_id=user.telegram_id,
        user=user,
        flt=flt,
        bybit_client=bybit_client,
        session_factory=factory,
        state_repo=RedisTrackingStateRepo(redis_client),
        buffer=RedisOrderBuffer(redis_client),
        view_messages=ViewMessages(redis_client),
        registry=EngineRegistry(),
    )


# ─── Tests ───────────────────────────────────────────────────────────


def test_url_builder_uses_inapp_redirect():
    url = build_order_url("123", "USDT", "RUB", 0)
    assert url.startswith("https://app.bybit.com/inapp")
    assert "by_dp=" in url
    assert "by_web_link=" in url
    assert "bybitapp" in url


def test_url_builder_buy_path_encoded():
    url = build_order_url("123", "USDT", "RUB", 0)
    assert "p2p%2Fbuy%2FUSDT%2FRUB" in url
    assert "adNo%3D123" in url


def test_url_builder_sell_path_encoded():
    url = build_order_url("123", "USDT", "RUB", 1)
    assert "p2p%2Fsell%2FUSDT%2FRUB" in url


async def test_send_initial_messages_with_ads(db_session, redis_client, sample_ads):
    user, flt = await _setup_user_and_filter(db_session)
    bot = _fake_bot()
    engine = _make_engine(bot, user, flt, redis_client, db_session,
                          _fake_bybit_client(sample_ads))

    await engine._send_initial_messages()

    # 1 header + 5 order messages
    assert bot.send_message.await_count == 6

    # Header text contains the filter name
    header_call = bot.send_message.await_args_list[0]
    assert "Тест" in header_call.args[1]

    # Buffer should hold the leftover ads
    buf = RedisOrderBuffer(redis_client)
    assert await buf.length(user.telegram_id) == len(sample_ads) - 5

    # State must be saved
    state = await RedisTrackingStateRepo(redis_client).get(user.telegram_id)
    assert state is not None
    assert state.filter_id == flt.id
    assert len(state.order_message_ids) == 5


async def test_send_initial_messages_empty(db_session, redis_client):
    user, flt = await _setup_user_and_filter(db_session)
    bot = _fake_bot()
    engine = _make_engine(bot, user, flt, redis_client, db_session, _fake_bybit_client([]))

    await engine._send_initial_messages()

    # Only the header
    assert bot.send_message.await_count == 1
    text = bot.send_message.await_args.args[1]
    assert "не найдено" in text.lower()


async def test_refresh_replaces_messages(db_session, redis_client, sample_ads):
    user, flt = await _setup_user_and_filter(db_session)
    bot = _fake_bot()
    engine = _make_engine(bot, user, flt, redis_client, db_session,
                          _fake_bybit_client(sample_ads))

    # Initial: 5 messages displayed
    await engine._send_initial_messages()
    initial_send_count = bot.send_message.await_count
    initial_order_ids = list(engine._order_message_ids)

    # Refresh — same ads, but engine rebuilds messages
    await engine._refresh_once()

    # 5 deletions + 5 new sends
    assert bot.delete_message.await_count == 5
    deleted_ids = [c.args[1] for c in bot.delete_message.await_args_list]
    assert sorted(deleted_ids) == sorted(initial_order_ids)
    assert bot.send_message.await_count == initial_send_count + 5

    # Header was edited
    bot.edit_message_text.assert_awaited()


async def test_refresh_on_api_error_keeps_orders(db_session, redis_client, sample_ads):
    user, flt = await _setup_user_and_filter(db_session)
    bot = _fake_bot()
    # First call succeeds (init), second raises
    fake_client = MagicMock()
    call_count = {"n": 0}

    async def get_online_ads(**kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return AdsListResult(count=len(sample_ads), items=sample_ads)
        raise BybitTimeoutError("timeout")

    fake_client.get_online_ads = get_online_ads
    engine = _make_engine(bot, user, flt, redis_client, db_session, fake_client)

    await engine._send_initial_messages()
    bot.delete_message.reset_mock()

    await engine._refresh_once()

    # Header edited (with error message), but no order deletions
    bot.edit_message_text.assert_awaited()
    error_text = bot.edit_message_text.await_args.kwargs.get("text") or \
                 bot.edit_message_text.await_args.args[0]
    assert "таймаут" in error_text.lower() or "повтор" in error_text.lower()
    assert bot.delete_message.await_count == 0


async def test_reject_blacklists_description_and_pops_next(
    db_session, redis_client, sample_ads,
):
    user, flt = await _setup_user_and_filter(db_session)
    bot = _fake_bot()
    engine = _make_engine(bot, user, flt, redis_client, db_session,
                          _fake_bybit_client(sample_ads))
    await engine._send_initial_messages()

    # Pick the first displayed ad and its message_id
    first_msg_id = engine._order_message_ids[0]
    first_ad = engine._displayed[first_msg_id]
    initial_buffer_len = await RedisOrderBuffer(redis_client).length(user.telegram_id)

    handled = await engine.reject_order(first_msg_id)
    await db_session.commit()

    assert handled is True

    # Description was added to the user's personal blacklist
    from db.repositories import BlacklistRepo
    from services.hashing import hash_description

    hashes = await BlacklistRepo(db_session).get_hashes_by_user(user.id)
    assert hash_description(first_ad.remark) in hashes

    # Old message was deleted
    deleted = [c.args[1] for c in bot.delete_message.await_args_list]
    assert first_msg_id in deleted

    # Buffer shrank by one (one ad popped to take the rejected slot)
    new_buffer_len = await RedisOrderBuffer(redis_client).length(user.telegram_id)
    assert new_buffer_len == initial_buffer_len - 1

    # Replacement message was sent → order_message_ids still has 5 ids
    assert len(engine._order_message_ids) == 5
    assert first_msg_id not in engine._order_message_ids


async def test_reject_when_buffer_empty(db_session, redis_client, sample_ads):
    user, flt = await _setup_user_and_filter(db_session)
    bot = _fake_bot()
    engine = _make_engine(bot, user, flt, redis_client, db_session,
                          _fake_bybit_client(sample_ads))
    await engine._send_initial_messages()

    # Drain buffer
    await RedisOrderBuffer(redis_client).clear(user.telegram_id)

    first_msg_id = engine._order_message_ids[0]
    handled = await engine.reject_order(first_msg_id)
    await db_session.commit()

    assert handled is True
    # Now only 4 displayed
    assert len(engine._order_message_ids) == 4
    assert first_msg_id not in engine._order_message_ids


async def test_reject_unknown_message_id_returns_false(
    db_session, redis_client, sample_ads,
):
    user, flt = await _setup_user_and_filter(db_session)
    bot = _fake_bot()
    engine = _make_engine(bot, user, flt, redis_client, db_session,
                          _fake_bybit_client(sample_ads))
    await engine._send_initial_messages()

    handled = await engine.reject_order(99999)
    assert handled is False


async def test_reject_ad_without_description_skips_blacklist(
    db_session, redis_client, sample_ads,
):
    """The ad with id='a3' in fixtures has remark=None."""
    user, flt = await _setup_user_and_filter(db_session)
    bot = _fake_bot()
    engine = _make_engine(bot, user, flt, redis_client, db_session,
                          _fake_bybit_client(sample_ads))
    await engine._send_initial_messages()

    # Find the message_id for ad without remark
    target_msg_id = next(
        mid for mid, ad in engine._displayed.items() if not (ad.remark or "").strip()
    )

    from db.repositories import BlacklistRepo

    handled = await engine.reject_order(target_msg_id)
    await db_session.commit()

    assert handled is True
    hashes = await BlacklistRepo(db_session).get_hashes_by_user(user.id)
    assert hashes == set()  # nothing blacklisted


async def test_stop_cleans_up(db_session, redis_client, sample_ads):
    user, flt = await _setup_user_and_filter(db_session)
    bot = _fake_bot()
    registry = EngineRegistry()
    engine = _make_engine(bot, user, flt, redis_client, db_session,
                          _fake_bybit_client(sample_ads))
    engine._registry = registry
    registry.register(user.telegram_id, engine)

    await engine._send_initial_messages()
    initial_orders = list(engine._order_message_ids)

    await engine.stop()

    # All order messages deleted
    deleted_ids = {c.args[1] for c in bot.delete_message.await_args_list}
    assert set(initial_orders).issubset(deleted_ids)

    # Header edited to "stopped"
    bot.edit_message_text.assert_awaited()

    # Redis cleared
    state = await RedisTrackingStateRepo(redis_client).get(user.telegram_id)
    assert state is None
    buf = RedisOrderBuffer(redis_client)
    assert await buf.length(user.telegram_id) == 0

    # Unregistered
    assert registry.get(user.telegram_id) is None
