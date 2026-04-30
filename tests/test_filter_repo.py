from decimal import Decimal

import pytest

from db.repositories import FilterRepo, UserRepo

pytestmark = pytest.mark.integration


async def _make_user(db_session, telegram_id: int = 1):
    user = await UserRepo(db_session).get_or_create(telegram_id, username=None)
    await db_session.commit()
    return user


async def test_create_and_get_by_id(db_session):
    user = await _make_user(db_session)
    repo = FilterRepo(db_session)

    flt = await repo.create(
        user_id=user.id,
        name="Утренний",
        currency_id="RUB",
        side=0,
        min_amount=Decimal("500"),
        max_amount=Decimal("50000"),
    )
    await db_session.commit()

    fetched = await repo.get_by_id(flt.id, user.id)
    assert fetched is not None
    assert fetched.name == "Утренний"
    assert fetched.min_amount == Decimal("500.00")


async def test_get_by_id_owner_check(db_session):
    user_a = await _make_user(db_session, telegram_id=1)
    user_b = await _make_user(db_session, telegram_id=2)
    repo = FilterRepo(db_session)

    flt = await repo.create(user_id=user_a.id, name="x", currency_id="RUB", side=0)
    await db_session.commit()

    assert await repo.get_by_id(flt.id, user_b.id) is None
    assert await repo.get_by_id(flt.id, user_a.id) is not None


async def test_name_exists_with_exclude(db_session):
    user = await _make_user(db_session)
    repo = FilterRepo(db_session)

    flt = await repo.create(user_id=user.id, name="A", currency_id="RUB", side=0)
    await db_session.commit()

    assert await repo.name_exists(user.id, "A") is True
    assert await repo.name_exists(user.id, "A", exclude_id=flt.id) is False
    assert await repo.name_exists(user.id, "B") is False


async def test_get_all_by_user_returns_only_owned(db_session):
    user_a = await _make_user(db_session, telegram_id=1)
    user_b = await _make_user(db_session, telegram_id=2)
    repo = FilterRepo(db_session)

    await repo.create(user_id=user_a.id, name="a1", currency_id="RUB", side=0)
    await repo.create(user_id=user_a.id, name="a2", currency_id="USD", side=1)
    await repo.create(user_id=user_b.id, name="b1", currency_id="RUB", side=0)
    await db_session.commit()

    a_filters = await repo.get_all_by_user(user_a.id)
    assert {f.name for f in a_filters} == {"a1", "a2"}


async def test_update_round_trip(db_session):
    user = await _make_user(db_session)
    repo = FilterRepo(db_session)

    flt = await repo.create(user_id=user.id, name="x", currency_id="RUB", side=0)
    await db_session.commit()

    updated = await repo.update(
        flt.id, user.id, name="renamed", min_amount=Decimal("100")
    )
    await db_session.commit()

    assert updated is not None
    assert updated.name == "renamed"
    assert updated.min_amount == Decimal("100.00")


async def test_delete(db_session):
    user = await _make_user(db_session)
    repo = FilterRepo(db_session)

    flt = await repo.create(user_id=user.id, name="x", currency_id="RUB", side=0)
    await db_session.commit()

    assert await repo.delete(flt.id, user.id) is True
    await db_session.commit()
    assert await repo.get_by_id(flt.id, user.id) is None

    # Deleting again is a no-op
    assert await repo.delete(flt.id, user.id) is False
