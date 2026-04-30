from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import User


class UserRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        result = await self._session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def create(self, telegram_id: int, username: str | None) -> User:
        user = User(telegram_id=telegram_id, username=username)
        self._session.add(user)
        await self._session.flush()
        return user

    async def get_or_create(self, telegram_id: int, username: str | None) -> User:
        existing = await self.get_by_telegram_id(telegram_id)
        if existing is not None:
            return existing
        try:
            return await self.create(telegram_id, username)
        except IntegrityError:
            await self._session.rollback()
            existing = await self.get_by_telegram_id(telegram_id)
            assert existing is not None
            return existing

    async def update_last_active(self, user_id: int) -> None:
        from sqlalchemy import func

        await self._session.execute(
            update(User)
            .where(User.id == user_id)
            .values(last_active_at=func.now())
        )
