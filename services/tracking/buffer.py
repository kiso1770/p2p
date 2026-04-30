from redis.asyncio import Redis

from services.bybit_models import BybitAd


def _key(telegram_id: int) -> str:
    return f"tracking_buffer:{telegram_id}"


class RedisOrderBuffer:
    """FIFO buffer of pre-fetched ads in Redis (List).

    The tracking engine pulls top-N ads from the API, stores them here,
    displays the first 5, and pops the next one when a user marks an
    order as 'not suitable'.
    """

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def set(self, telegram_id: int, ads: list[BybitAd]) -> None:
        """Replace the whole buffer atomically."""
        key = _key(telegram_id)
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.delete(key)
            if ads:
                pipe.rpush(key, *(ad.model_dump_json(by_alias=True) for ad in ads))
            await pipe.execute()

    async def peek(self, telegram_id: int, n: int) -> list[BybitAd]:
        raw = await self._redis.lrange(_key(telegram_id), 0, n - 1)
        return [BybitAd.model_validate_json(item) for item in raw]

    async def pop_next(self, telegram_id: int) -> BybitAd | None:
        raw = await self._redis.lpop(_key(telegram_id))
        if raw is None:
            return None
        return BybitAd.model_validate_json(raw)

    async def clear(self, telegram_id: int) -> None:
        await self._redis.delete(_key(telegram_id))

    async def length(self, telegram_id: int) -> int:
        return await self._redis.llen(_key(telegram_id))
