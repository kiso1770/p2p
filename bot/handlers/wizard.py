"""Filter creation wizard (Phase 5b)."""
import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.currencies import CURRENCIES, currency_flag
from bot.handlers.edit import open_editor_for
from bot.handlers.filters import render_filters_view
from bot.keyboards.wizard import (
    currency_picker_kb,
    name_input_kb,
    side_picker_kb,
)
from bot.states.wizard import CreateFilter
from bot.views import ViewMessages, delete_current_view
from db.models import User
from db.repositories import FilterRepo

logger = logging.getLogger(__name__)
router = Router(name=__name__)

STEP_CURRENCY = (
    "<b>➕ Новый фильтр — шаг 1 из 3</b>\n\n"
    "Выберите фиатную валюту:"
)
STEP_SIDE = (
    "<b>➕ Новый фильтр — шаг 2 из 3</b>\n\n"
    "Валюта: {flag} {currency}\n\n"
    "Выберите тип сделки:"
)
STEP_NAME = (
    "<b>➕ Новый фильтр — шаг 3 из 3</b>\n\n"
    "Валюта: {flag} {currency} • {side_text}\n\n"
    "Введите название фильтра текстом (1–32 символа)."
)
ERROR_PREFIX = "⚠️ <b>{error}</b>\n\n"


def _side_text(side: int) -> str:
    return "📈 Покупка" if side == 0 else "📉 Продажа"


def _build_step_side(currency_id: str) -> str:
    return STEP_SIDE.format(flag=currency_flag(currency_id), currency=currency_id)


def _build_step_name(currency_id: str, side: int) -> str:
    return STEP_NAME.format(
        flag=currency_flag(currency_id),
        currency=currency_id,
        side_text=_side_text(side),
    )


# ─── Entry point ─────────────────────────────────────────────────────


@router.callback_query(F.data == "filter:create")
async def start_wizard(
    callback: CallbackQuery,
    bot: Bot,
    view_messages: ViewMessages,
    state: FSMContext,
) -> None:
    chat_id = callback.message.chat.id
    await delete_current_view(bot, chat_id, view_messages)

    sent = await bot.send_message(chat_id, STEP_CURRENCY, reply_markup=currency_picker_kb())
    await view_messages.set(chat_id, [sent.message_id])
    await state.clear()
    await state.set_state(CreateFilter.choosing_currency)
    await callback.answer()


# ─── Step transitions ────────────────────────────────────────────────


@router.callback_query(F.data.startswith("wiz:cur_page:"), CreateFilter.choosing_currency)
async def change_currency_page(callback: CallbackQuery, state: FSMContext) -> None:
    page = int(callback.data.split(":")[2])
    await callback.message.edit_reply_markup(reply_markup=currency_picker_kb(page))
    await callback.answer()


@router.callback_query(F.data == "wiz:noop")
async def noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data.startswith("wiz:cur:"), CreateFilter.choosing_currency)
async def chose_currency(callback: CallbackQuery, state: FSMContext) -> None:
    code = callback.data.split(":")[2]
    if code not in CURRENCIES:
        await callback.answer("Неизвестная валюта", show_alert=True)
        return
    await state.update_data(currency_id=code)
    await callback.message.edit_text(
        _build_step_side(code), reply_markup=side_picker_kb(code)
    )
    await state.set_state(CreateFilter.choosing_side)
    await callback.answer()


@router.callback_query(F.data.startswith("wiz:side:"), CreateFilter.choosing_side)
async def chose_side(callback: CallbackQuery, state: FSMContext) -> None:
    side = int(callback.data.split(":")[2])
    if side not in (0, 1):
        await callback.answer("Некорректный тип", show_alert=True)
        return
    data = await state.update_data(side=side)
    await callback.message.edit_text(
        _build_step_name(data["currency_id"], side), reply_markup=name_input_kb()
    )
    await state.set_state(CreateFilter.entering_name)
    await callback.answer()


@router.callback_query(F.data == "wiz:back", CreateFilter.choosing_side)
async def back_to_currency(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.message.edit_text(STEP_CURRENCY, reply_markup=currency_picker_kb())
    await state.set_state(CreateFilter.choosing_currency)
    await callback.answer()


@router.callback_query(F.data == "wiz:back", CreateFilter.entering_name)
async def back_to_side(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    await callback.message.edit_text(
        _build_step_side(data["currency_id"]), reply_markup=side_picker_kb(data["currency_id"])
    )
    await state.set_state(CreateFilter.choosing_side)
    await callback.answer()


# ─── Cancel ──────────────────────────────────────────────────────────


@router.callback_query(F.data == "wiz:cancel")
async def cancel_wizard(
    callback: CallbackQuery,
    bot: Bot,
    user: User,
    session: AsyncSession,
    view_messages: ViewMessages,
    state: FSMContext,
) -> None:
    await state.clear()
    await render_filters_view(bot, callback.message.chat.id, user, session, view_messages)
    await callback.answer("Создание отменено")


# ─── Final step: name input ──────────────────────────────────────────


@router.message(CreateFilter.entering_name)
async def receive_name(
    message: Message,
    bot: Bot,
    user: User,
    session: AsyncSession,
    view_messages: ViewMessages,
    state: FSMContext,
) -> None:
    chat_id = message.chat.id
    name = (message.text or "").strip()

    # Best-effort delete of the user's input message
    try:
        await bot.delete_message(chat_id, message.message_id)
    except Exception:  # noqa: BLE001
        pass

    error: str | None = None
    if not name:
        error = "Имя не может быть пустым"
    elif len(name) > 32:
        error = "Максимум 32 символа"
    else:
        repo = FilterRepo(session)
        if await repo.name_exists(user.id, name):
            error = f"Фильтр с именем «{name}» уже существует"

    data = await state.get_data()

    if error is not None:
        view_ids = await view_messages.get(chat_id)
        if not view_ids:
            return
        wizard_msg_id = view_ids[0]
        text = ERROR_PREFIX.format(error=error) + _build_step_name(
            data["currency_id"], data["side"]
        )
        try:
            await bot.edit_message_text(
                text, chat_id, wizard_msg_id, reply_markup=name_input_kb()
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to edit wizard message: %s", exc)
        return

    # Success — create the filter, then redirect to the parameters editor
    flt = await FilterRepo(session).create(
        user_id=user.id,
        name=name,
        currency_id=data["currency_id"],
        side=data["side"],
    )
    await session.commit()
    await state.clear()
    await open_editor_for(bot, chat_id, flt, view_messages, state)
