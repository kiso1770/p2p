import logging

from aiogram import Bot, F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards.main_menu import main_menu_kb
from bot.views import ViewMessages, delete_current_view
from db.models import User
from services.tracking.buffer import RedisOrderBuffer
from services.tracking.lifecycle import stop_tracking
from services.tracking.registry import EngineRegistry
from services.tracking.state import RedisTrackingStateRepo

logger = logging.getLogger(__name__)
router = Router(name=__name__)


WELCOME_NEW = (
    "👋 <b>Добро пожаловать в P2P Monitor!</b>\n\n"
    "Бот отслеживает ордера на Bybit P2P и показывает только те,\n"
    "что подходят под ваши фильтры.\n\n"
    "Начните с создания первого фильтра."
)
WELCOME_BACK = "👋 С возвращением!"


@router.message(CommandStart())
async def handle_start(
    message: Message,
    user: User,
    is_new_user: bool,
    bot: Bot,
    state_repo: RedisTrackingStateRepo,
    buffer: RedisOrderBuffer,
    view_messages: ViewMessages,
    engine_registry: EngineRegistry,
    state: FSMContext,
) -> None:
    chat_id = message.chat.id
    await state.clear()

    stopped = await stop_tracking(
        bot, chat_id, state_repo, buffer, engine_registry=engine_registry
    )
    if stopped:
        logger.info("Stopped active tracking for user %s on /start", user.telegram_id)

    await delete_current_view(bot, chat_id, view_messages)

    text = WELCOME_NEW if is_new_user else WELCOME_BACK
    sent = await message.answer(text, reply_markup=main_menu_kb())
    await view_messages.set(chat_id, [sent.message_id])


@router.callback_query(F.data == "menu:settings")
async def menu_settings_stub(callback: CallbackQuery) -> None:
    await callback.answer("⚙️ Настройки — в разработке (Фаза 8)", show_alert=True)
