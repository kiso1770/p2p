import asyncio
import logging

import redis.asyncio as aioredis
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.redis import RedisStorage
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from bot.handlers import build_root_router
from bot.middlewares import DbSessionMiddleware, UserMiddleware
from bot.views import ViewMessages
from config import settings
from services.bybit_client import BybitClient
from services.tracking.buffer import RedisOrderBuffer
from services.tracking.registry import EngineRegistry
from services.tracking.state import RedisTrackingStateRepo

logger = logging.getLogger(__name__)


async def main() -> None:
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger.info("Starting P2P Monitor Bot...")

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode="HTML"),
    )

    redis_client = aioredis.from_url(settings.redis_url)
    fsm_storage = RedisStorage(redis_client)
    dp = Dispatcher(storage=fsm_storage)

    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    bybit_client = BybitClient(
        api_key=settings.bybit_api_key,
        api_secret=settings.bybit_api_secret,
        base_url=settings.bybit_base_url,
    )
    engine_registry = EngineRegistry()

    dp["state_repo"] = RedisTrackingStateRepo(redis_client)
    dp["buffer"] = RedisOrderBuffer(redis_client)
    dp["view_messages"] = ViewMessages(redis_client)
    dp["engine_registry"] = engine_registry
    dp["bybit_client"] = bybit_client
    dp["session_factory"] = session_factory

    dp.update.outer_middleware(DbSessionMiddleware(session_factory))
    user_middleware = UserMiddleware()
    dp.message.outer_middleware(user_middleware)
    dp.callback_query.outer_middleware(user_middleware)

    dp.include_router(build_root_router())

    try:
        me = await bot.get_me()
        logger.info("Bot connected: @%s (id=%s)", me.username, me.id)
        await dp.start_polling(bot)
    finally:
        logger.info("Shutting down — stopping all tracking engines...")
        await engine_registry.stop_all()
        await bybit_client.close()
        await bot.session.close()
        await redis_client.aclose()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
