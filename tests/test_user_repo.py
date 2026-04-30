import pytest

from db.repositories import UserRepo

pytestmark = pytest.mark.integration


async def test_get_or_create_inserts_new_user(db_session):
    repo = UserRepo(db_session)

    user = await repo.get_or_create(telegram_id=12345, username="alice")
    await db_session.commit()

    assert user.id is not None
    assert user.telegram_id == 12345
    assert user.username == "alice"


async def test_get_or_create_returns_existing(db_session):
    repo = UserRepo(db_session)

    first = await repo.get_or_create(telegram_id=42, username="bob")
    await db_session.commit()

    second = await repo.get_or_create(telegram_id=42, username="ignored")
    await db_session.commit()

    assert first.id == second.id
    assert second.username == "bob"


async def test_get_by_telegram_id_returns_none_when_missing(db_session):
    repo = UserRepo(db_session)
    assert await repo.get_by_telegram_id(999) is None


async def test_update_last_active(db_session):
    repo = UserRepo(db_session)
    user = await repo.get_or_create(telegram_id=1, username=None)
    await db_session.commit()

    initial = user.last_active_at

    import asyncio
    await asyncio.sleep(1.1)
    await repo.update_last_active(user.id)
    await db_session.commit()
    await db_session.refresh(user)

    assert user.last_active_at > initial
