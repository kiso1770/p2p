import asyncio
import logging

from aiogram import Bot, Dispatcher

from config import settings


async def main() -> None:
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger = logging.getLogger(__name__)
    logger.info("Starting P2P Monitor Bot...")

    bot = Bot(token=settings.bot_token)
    dp = Dispatcher()

    try:
        me = await bot.get_me()
        logger.info("Bot connected: @%s (id=%s)", me.username, me.id)
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
