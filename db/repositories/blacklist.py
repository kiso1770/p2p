from sqlalchemy import and_, delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import DescriptionBlacklist
from services.hashing import hash_description


class BlacklistRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_all_by_user(self, user_id: int) -> list[DescriptionBlacklist]:
        result = await self._session.execute(
            select(DescriptionBlacklist)
            .where(DescriptionBlacklist.user_id == user_id)
            .order_by(DescriptionBlacklist.created_at)
        )
        return list(result.scalars().all())

    async def get_hashes_by_user(self, user_id: int) -> set[str]:
        result = await self._session.execute(
            select(DescriptionBlacklist.description_hash).where(
                DescriptionBlacklist.user_id == user_id
            )
        )
        return set(result.scalars().all())

    async def add(
        self, user_id: int, description_text: str
    ) -> DescriptionBlacklist | None:
        """Idempotent. Returns the new entry, or None if already present.

        Uses INSERT ... ON CONFLICT DO NOTHING so that duplicates do not
        require a rollback (which would invalidate the surrounding
        transaction).
        """
        digest = hash_description(description_text)
        stmt = (
            pg_insert(DescriptionBlacklist)
            .values(
                user_id=user_id,
                description_hash=digest,
                description_text=description_text,
            )
            .on_conflict_do_nothing(index_elements=["user_id", "description_hash"])
            .returning(DescriptionBlacklist)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def delete_by_id(self, entry_id: int, user_id: int) -> bool:
        result = await self._session.execute(
            delete(DescriptionBlacklist).where(
                and_(
                    DescriptionBlacklist.id == entry_id,
                    DescriptionBlacklist.user_id == user_id,
                )
            )
        )
        return result.rowcount > 0

    async def delete_all_by_user(self, user_id: int) -> int:
        result = await self._session.execute(
            delete(DescriptionBlacklist).where(
                DescriptionBlacklist.user_id == user_id
            )
        )
        return result.rowcount
