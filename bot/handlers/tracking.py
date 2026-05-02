"""Tracking handlers (Phase 6a): start, stop. Order actions are stubs."""
import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.views import ViewMessages, delete_current_view
from db.models import User
from db.repositories import FilterRepo
from services.bybit_client import BybitClient
from services.tracking.buffer import RedisOrderBuffer
from services.tracking.engine import TrackingEngine
from services.tracking.lifecycle import stop_tracking
from services.tracking.registry import EngineRegistry
from services.tracking.state import RedisTrackingStateRepo

logger = logging.getLogger(__name__)
router = Router(name=__name__)


@router.callback_query(F.data.startswith("filter:start:"))
async def start_tracking(
    callback: CallbackQuery,
    bot: Bot,
    user: User,
    session: AsyncSession,
    view_messages: ViewMessages,
    state_repo: RedisTrackingStateRepo,
    buffer: RedisOrderBuffer,
    engine_registry: EngineRegistry,
    bybit_client: BybitClient,
    session_factory: async_sessionmaker,
    state: FSMContext,
) -> None:
    filter_id = int(callback.data.split(":")[2])
    flt = await FilterRepo(session).get_by_id(filter_id, user.id)
    if flt is None:
        await callback.answer("Фильтр не найден", show_alert=True)
        return

    chat_id = callback.message.chat.id

    # Stop any previous tracking (cancel engine + delete its messages)
    await engine_registry.stop_for(chat_id)
    await stop_tracking(bot, chat_id, state_repo, buffer)
    await delete_current_view(bot, chat_id, view_messages)
    await state.clear()

    engine = TrackingEngine(
        bot=bot,
        chat_id=chat_id,
        user=user,
        flt=flt,
        bybit_client=bybit_client,
        session_factory=session_factory,
        state_repo=state_repo,
        buffer=buffer,
        view_messages=view_messages,
        registry=engine_registry,
    )
    engine_registry.register(chat_id, engine)
    await engine.start()
    await callback.answer()


@router.callback_query(F.data == "tracking:stop")
async def stop_tracking_handler(
    callback: CallbackQuery,
    engine_registry: EngineRegistry,
) -> None:
    stopped = await engine_registry.stop_for(callback.message.chat.id)
    if not stopped:
        await callback.answer("Отслеживание не активно", show_alert=True)
        return
    await callback.answer("Остановлено")


@router.callback_query(F.data.startswith("order:reject:"))
async def reject_order(
    callback: CallbackQuery,
    engine_registry: EngineRegistry,
) -> None:
    chat_id = callback.message.chat.id
    engine = engine_registry.get(chat_id)
    if engine is None:
        await callback.answer("Отслеживание не активно", show_alert=True)
        return

    handled = await engine.reject_order(callback.message.message_id)
    if not handled:
        await callback.answer("Этот ордер уже скрыт", show_alert=False)
        return

    await callback.answer(
        "✅ Ордер скрыт. Описание добавлено в чёрный список.",
        show_alert=False,
    )
