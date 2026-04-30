import pytest

from db.repositories import BlacklistRepo, UserRepo
from services.hashing import hash_description

pytestmark = pytest.mark.integration


async def _make_user(db_session, telegram_id: int = 1):
    user = await UserRepo(db_session).get_or_create(telegram_id, username=None)
    await db_session.commit()
    return user


async def test_add_and_get_hashes(db_session):
    user = await _make_user(db_session)
    repo = BlacklistRepo(db_session)

    entry = await repo.add(user.id, "СБП Тинькофф")
    await db_session.commit()

    assert entry is not None
    assert entry.description_hash == hash_description("СБП Тинькофф")

    hashes = await repo.get_hashes_by_user(user.id)
    assert hashes == {hash_description("СБП Тинькофф")}


async def test_add_idempotent(db_session):
    user = await _make_user(db_session)
    repo = BlacklistRepo(db_session)

    first = await repo.add(user.id, "duplicate")
    await db_session.commit()
    assert first is not None

    second = await repo.add(user.id, "duplicate")
    await db_session.commit()
    assert second is None  # already exists

    entries = await repo.get_all_by_user(user.id)
    assert len(entries) == 1


async def test_normalisation_treats_whitespace_and_case_as_same(db_session):
    user = await _make_user(db_session)
    repo = BlacklistRepo(db_session)

    await repo.add(user.id, "  Hello World  ")
    await db_session.commit()
    assert await repo.add(user.id, "hello world") is None
    await db_session.commit()


async def test_delete_by_id_owner_check(db_session):
    user_a = await _make_user(db_session, telegram_id=1)
    user_b = await _make_user(db_session, telegram_id=2)
    repo = BlacklistRepo(db_session)

    entry = await repo.add(user_a.id, "secret")
    await db_session.commit()
    assert entry is not None

    assert await repo.delete_by_id(entry.id, user_b.id) is False
    await db_session.commit()
    assert await repo.delete_by_id(entry.id, user_a.id) is True
    await db_session.commit()


async def test_delete_all_by_user_returns_count(db_session):
    user = await _make_user(db_session)
    repo = BlacklistRepo(db_session)

    for text in ("a", "b", "c"):
        await repo.add(user.id, text)
    await db_session.commit()

    assert await repo.delete_all_by_user(user.id) == 3
    await db_session.commit()
    assert await repo.get_all_by_user(user.id) == []
