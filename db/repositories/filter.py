from typing import Any

from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Filter


class FilterRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, filter_id: int, user_id: int) -> Filter | None:
        result = await self._session.execute(
            select(Filter).where(
                and_(Filter.id == filter_id, Filter.user_id == user_id)
            )
        )
        return result.scalar_one_or_none()

    async def get_all_by_user(self, user_id: int) -> list[Filter]:
        result = await self._session.execute(
            select(Filter)
            .where(Filter.user_id == user_id)
            .order_by(Filter.currency_id, Filter.side, Filter.created_at)
        )
        return list(result.scalars().all())

    async def name_exists(
        self, user_id: int, name: str, exclude_id: int | None = None
    ) -> bool:
        stmt = select(Filter.id).where(
            and_(Filter.user_id == user_id, Filter.name == name)
        )
        if exclude_id is not None:
            stmt = stmt.where(Filter.id != exclude_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def create(
        self,
        user_id: int,
        name: str,
        currency_id: str,
        side: int,
        token_id: str = "USDT",
        **params: Any,
    ) -> Filter:
        flt = Filter(
            user_id=user_id,
            name=name,
            token_id=token_id,
            currency_id=currency_id,
            side=side,
            **params,
        )
        self._session.add(flt)
        await self._session.flush()
        return flt

    async def update(self, filter_id: int, user_id: int, **fields: Any) -> Filter | None:
        flt = await self.get_by_id(filter_id, user_id)
        if flt is None:
            return None
        for key, value in fields.items():
            setattr(flt, key, value)
        await self._session.flush()
        return flt

    async def delete(self, filter_id: int, user_id: int) -> bool:
        result = await self._session.execute(
            delete(Filter).where(
                and_(Filter.id == filter_id, Filter.user_id == user_id)
            )
        )
        return result.rowcount > 0
