import json
from dataclasses import asdict, dataclass, field
from typing import Literal

from redis.asyncio import Redis

TrackingStatus = Literal["ACTIVE", "STOPPED"]


@dataclass
class TrackingState:
    filter_id: int
    header_message_id: int
    last_activity_at: float
    status: TrackingStatus = "ACTIVE"
    order_message_ids: list[int] = field(default_factory=list)


def _key(telegram_id: int) -> str:
    return f"tracking:{telegram_id}"


class RedisTrackingStateRepo:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def get(self, telegram_id: int) -> TrackingState | None:
        raw = await self._redis.hgetall(_key(telegram_id))
        if not raw:
            return None
        data = {k.decode() if isinstance(k, bytes) else k: v for k, v in raw.items()}
        decoded = {k: (v.decode() if isinstance(v, bytes) else v) for k, v in data.items()}
        return TrackingState(
            filter_id=int(decoded["filter_id"]),
            header_message_id=int(decoded["header_message_id"]),
            order_message_ids=json.loads(decoded.get("order_message_ids", "[]")),
            last_activity_at=float(decoded["last_activity_at"]),
            status=decoded.get("status", "ACTIVE"),  # type: ignore[arg-type]
        )

    async def set(self, telegram_id: int, state: TrackingState) -> None:
        data = asdict(state)
        data["order_message_ids"] = json.dumps(data["order_message_ids"])
        await self._redis.hset(_key(telegram_id), mapping=data)

    async def delete(self, telegram_id: int) -> None:
        await self._redis.delete(_key(telegram_id))

    async def update_activity(self, telegram_id: int, timestamp: float) -> None:
        await self._redis.hset(_key(telegram_id), "last_activity_at", timestamp)

    async def update_message_ids(
        self, telegram_id: int, header_id: int, order_ids: list[int]
    ) -> None:
        await self._redis.hset(
            _key(telegram_id),
            mapping={
                "header_message_id": header_id,
                "order_message_ids": json.dumps(order_ids),
            },
        )
