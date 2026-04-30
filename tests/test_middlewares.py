"""Integration tests for DbSessionMiddleware and UserMiddleware."""
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.middlewares import DbSessionMiddleware, UserMiddleware
from db.models import User
from tests.conftest import TEST_DATABASE_URL

pytestmark = pytest.mark.integration


def _fake_message(telegram_id: int, username: str | None = "alice"):
    """Build a duck-typed Message-like object that satisfies isinstance checks."""
    from aiogram.types import Message
    msg = MagicMock(spec=Message)
    msg.from_user = MagicMock(id=telegram_id, username=username)
    return msg


@pytest.fixture
async def session_factory(db_session):
    return async_sessionmaker(db_session.bind, expire_on_commit=False)


async def test_db_session_middleware_commits_on_success(session_factory):
    middleware = DbSessionMiddleware(session_factory)

    async def handler(event, data):
        from db.repositories import UserRepo
        await UserRepo(data["session"]).create(telegram_id=10, username="x")
        return "ok"

    result = await middleware(handler, _fake_message(10), {})
    assert result == "ok"

    # Verify the row was committed
    async with session_factory() as session:
        found = (await session.execute(select(User).where(User.telegram_id == 10))).scalar_one()
        assert found.username == "x"


async def test_db_session_middleware_rolls_back_on_exception(session_factory):
    middleware = DbSessionMiddleware(session_factory)

    async def handler(event, data):
        from db.repositories import UserRepo
        await UserRepo(data["session"]).create(telegram_id=11, username="x")
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        await middleware(handler, _fake_message(11), {})

    async with session_factory() as session:
        found = (await session.execute(select(User).where(User.telegram_id == 11))).scalar_one_or_none()
        assert found is None


async def test_user_middleware_creates_new_user(db_session):
    middleware = UserMiddleware()

    captured = {}
    async def handler(event, data):
        captured["user"] = data["user"]
        captured["is_new_user"] = data["is_new_user"]

    await middleware(handler, _fake_message(100, "newbie"), {"session": db_session})
    await db_session.commit()

    assert captured["is_new_user"] is True
    assert captured["user"].telegram_id == 100
    assert captured["user"].username == "newbie"


async def test_user_middleware_returns_existing(db_session):
    middleware = UserMiddleware()

    # First call — new user
    await middleware(lambda e, d: AsyncMock()(e, d), _fake_message(101, "old"), {"session": db_session})
    await db_session.commit()

    captured = {}
    async def handler(event, data):
        captured["is_new_user"] = data["is_new_user"]
        captured["user_id"] = data["user"].id

    await middleware(handler, _fake_message(101, "old"), {"session": db_session})
    await db_session.commit()

    assert captured["is_new_user"] is False
    assert captured["user_id"] is not None


async def test_user_middleware_updates_last_active(db_session):
    middleware = UserMiddleware()

    async def noop(event, data):
        pass

    # Create
    await middleware(noop, _fake_message(102, "u"), {"session": db_session})
    await db_session.commit()

    user_after_create = (
        await db_session.execute(select(User).where(User.telegram_id == 102))
    ).scalar_one()
    initial_active = user_after_create.last_active_at

    import asyncio
    await asyncio.sleep(1.1)

    # Re-trigger
    await middleware(noop, _fake_message(102, "u"), {"session": db_session})
    await db_session.commit()
    await db_session.refresh(user_after_create)

    assert user_after_create.last_active_at > initial_active
