import pytest

from services.tracking.buffer import RedisOrderBuffer

pytestmark = pytest.mark.integration


async def test_set_and_peek(redis_client, sample_ads):
    buf = RedisOrderBuffer(redis_client)
    await buf.set(1, sample_ads)

    first_three = await buf.peek(1, 3)
    assert [a.id for a in first_three] == ["a1", "a2", "a3"]

    assert await buf.length(1) == len(sample_ads)


async def test_pop_next(redis_client, sample_ads):
    buf = RedisOrderBuffer(redis_client)
    await buf.set(1, sample_ads)

    popped = await buf.pop_next(1)
    assert popped is not None
    assert popped.id == "a1"
    assert await buf.length(1) == len(sample_ads) - 1


async def test_pop_next_returns_none_when_empty(redis_client):
    buf = RedisOrderBuffer(redis_client)
    assert await buf.pop_next(1) is None


async def test_set_replaces_existing(redis_client, sample_ads):
    buf = RedisOrderBuffer(redis_client)
    await buf.set(1, sample_ads)
    await buf.set(1, sample_ads[:2])
    assert await buf.length(1) == 2


async def test_clear(redis_client, sample_ads):
    buf = RedisOrderBuffer(redis_client)
    await buf.set(1, sample_ads)
    await buf.clear(1)
    assert await buf.length(1) == 0


async def test_set_empty_list(redis_client):
    buf = RedisOrderBuffer(redis_client)
    await buf.set(1, [])
    assert await buf.length(1) == 0
    assert await buf.peek(1, 5) == []
