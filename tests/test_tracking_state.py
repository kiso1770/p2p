import time

import pytest

from services.tracking.state import RedisTrackingStateRepo, TrackingState

pytestmark = pytest.mark.integration


async def test_set_get_round_trip(redis_client):
    repo = RedisTrackingStateRepo(redis_client)

    state = TrackingState(
        filter_id=42,
        header_message_id=1001,
        order_message_ids=[1002, 1003, 1004],
        last_activity_at=time.time(),
        status="ACTIVE",
    )
    await repo.set(telegram_id=12345, state=state)

    fetched = await repo.get(12345)
    assert fetched is not None
    assert fetched.filter_id == 42
    assert fetched.header_message_id == 1001
    assert fetched.order_message_ids == [1002, 1003, 1004]
    assert fetched.status == "ACTIVE"


async def test_get_returns_none_when_missing(redis_client):
    repo = RedisTrackingStateRepo(redis_client)
    assert await repo.get(99999) is None


async def test_delete(redis_client):
    repo = RedisTrackingStateRepo(redis_client)
    state = TrackingState(
        filter_id=1, header_message_id=1, last_activity_at=time.time(),
    )
    await repo.set(1, state)
    await repo.delete(1)
    assert await repo.get(1) is None


async def test_update_activity_does_not_touch_other_fields(redis_client):
    repo = RedisTrackingStateRepo(redis_client)
    state = TrackingState(
        filter_id=7,
        header_message_id=500,
        order_message_ids=[501, 502],
        last_activity_at=1.0,
    )
    await repo.set(1, state)

    await repo.update_activity(1, 999.5)

    fetched = await repo.get(1)
    assert fetched is not None
    assert fetched.last_activity_at == 999.5
    assert fetched.filter_id == 7
    assert fetched.order_message_ids == [501, 502]


async def test_update_message_ids(redis_client):
    repo = RedisTrackingStateRepo(redis_client)
    state = TrackingState(
        filter_id=1,
        header_message_id=10,
        order_message_ids=[11, 12],
        last_activity_at=1.0,
    )
    await repo.set(1, state)

    await repo.update_message_ids(1, header_id=20, order_ids=[21, 22, 23])

    fetched = await repo.get(1)
    assert fetched is not None
    assert fetched.header_message_id == 20
    assert fetched.order_message_ids == [21, 22, 23]
    assert fetched.last_activity_at == 1.0  # untouched
