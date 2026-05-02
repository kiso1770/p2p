"""Filter parameters editor (Phase 5c).

Single-message editor with FSM-driven sub-flows for each parameter group:
amount range, price range, experience/reputation, description filter,
sort & count.

Eager-save model: every committed change is written to the DB immediately.
"Back" buttons abort sub-flow without applying intermediate values.
"""
from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.handlers.filters import render_filters_view
from bot.keyboards.edit import (
    description_kb,
    experience_kb,
    main_editor_kb,
    sort_kb,
    step_input_kb,
)
from bot.keyboards.filters import format_filter
from bot.states.wizard import EditFilter
from bot.views import ViewMessages, delete_current_view
from db.models import Filter, User
from db.repositories import FilterRepo

logger = logging.getLogger(__name__)
router = Router(name=__name__)

ERROR_PREFIX = "⚠️ <b>{error}</b>\n\n"


# ─── Render helpers ──────────────────────────────────────────────────


async def _render_main(
    bot: Bot, chat_id: int, flt: Filter, view_messages: ViewMessages
) -> int:
    """Send/replace the main editor message; return its message_id."""
    await delete_current_view(bot, chat_id, view_messages)
    text = "⚙️ <b>Редактирование фильтра</b>\n\n" + format_filter(flt)
    sent = await bot.send_message(chat_id, text, reply_markup=main_editor_kb())
    await view_messages.set(chat_id, [sent.message_id])
    return sent.message_id


async def _edit_main(
    bot: Bot, chat_id: int, msg_id: int, flt: Filter
) -> None:
    text = "⚙️ <b>Редактирование фильтра</b>\n\n" + format_filter(flt)
    try:
        await bot.edit_message_text(text, chat_id=chat_id, message_id=msg_id, reply_markup=main_editor_kb())
    except Exception as exc:  # noqa: BLE001
        logger.warning("edit_main failed: %s", exc)


async def _open_editor(
    bot: Bot,
    chat_id: int,
    flt: Filter,
    view_messages: ViewMessages,
    state: FSMContext,
) -> None:
    msg_id = await _render_main(bot, chat_id, flt, view_messages)
    await state.set_state(EditFilter.main)
    await state.update_data(filter_id=flt.id, msg_id=msg_id)


async def _load_filter(session: AsyncSession, user: User, state: FSMContext) -> Filter | None:
    data = await state.get_data()
    fid = data.get("filter_id")
    if fid is None:
        return None
    return await FilterRepo(session).get_by_id(fid, user.id)


# ─── Entry point: filter:edit:{id} ───────────────────────────────────


async def open_editor_for(
    bot: Bot,
    chat_id: int,
    flt: Filter,
    view_messages: ViewMessages,
    state: FSMContext,
) -> None:
    """Public helper used by the wizard to redirect into the editor."""
    await _open_editor(bot, chat_id, flt, view_messages, state)


@router.callback_query(F.data.startswith("filter:edit:"))
async def open_editor(
    callback: CallbackQuery,
    bot: Bot,
    user: User,
    session: AsyncSession,
    view_messages: ViewMessages,
    state: FSMContext,
) -> None:
    filter_id = int(callback.data.split(":")[2])
    flt = await FilterRepo(session).get_by_id(filter_id, user.id)
    if flt is None:
        await callback.answer("Фильтр не найден", show_alert=True)
        return
    await _open_editor(bot, callback.message.chat.id, flt, view_messages, state)
    await callback.answer()


# ─── Done: back to filters list ──────────────────────────────────────


@router.callback_query(F.data == "edit:done")
async def done_editing(
    callback: CallbackQuery,
    bot: Bot,
    user: User,
    session: AsyncSession,
    view_messages: ViewMessages,
    state: FSMContext,
) -> None:
    await state.clear()
    await render_filters_view(bot, callback.message.chat.id, user, session, view_messages)
    await callback.answer()


# ─── Group: amount range (2-step) ────────────────────────────────────


def _build_step_amount_min(flt: Filter, error: str | None = None) -> str:
    prefix = ERROR_PREFIX.format(error=error) if error else ""
    return (
        prefix
        + "💵 <b>Диапазон суммы сделки</b>\n\n"
        + f"Текущее: {flt.min_amount or '—'} – {flt.max_amount or '—'} USDT\n\n"
        + "Введите <b>минимальную</b> сумму (USDT, число) "
        + "или нажмите Пропустить, чтобы убрать ограничение."
    )


def _build_step_amount_max(pending_min: Decimal | None, error: str | None = None) -> str:
    prefix = ERROR_PREFIX.format(error=error) if error else ""
    min_text = f"{pending_min} USDT" if pending_min is not None else "не задан"
    return (
        prefix
        + "💵 <b>Диапазон суммы сделки</b>\n\n"
        + f"Минимум: {min_text} ✅\n\n"
        + "Введите <b>максимальную</b> сумму (USDT, число) "
        + "или нажмите Пропустить, чтобы убрать ограничение."
    )


@router.callback_query(F.data == "edit:group:amount", EditFilter.main)
async def group_amount(
    callback: CallbackQuery,
    bot: Bot,
    user: User,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    flt = await _load_filter(session, user, state)
    if flt is None:
        await callback.answer("Фильтр не найден", show_alert=True)
        return
    data = await state.get_data()
    await bot.edit_message_text(_build_step_amount_min(flt), chat_id=callback.message.chat.id, message_id=data["msg_id"], reply_markup=step_input_kb(),
    )
    await state.set_state(EditFilter.amount_min)
    await callback.answer()


def _parse_decimal_positive(text: str) -> Decimal | None:
    try:
        value = Decimal(text.replace(",", ".").strip())
    except InvalidOperation:
        return None
    if value < 0:
        return None
    return value


@router.message(EditFilter.amount_min)
async def receive_amount_min(
    message: Message,
    bot: Bot,
    user: User,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    chat_id = message.chat.id
    raw = (message.text or "").strip()
    try:
        await bot.delete_message(chat_id, message.message_id)
    except Exception:  # noqa: BLE001
        pass

    value = _parse_decimal_positive(raw)
    if value is None:
        flt = await _load_filter(session, user, state)
        data = await state.get_data()
        await bot.edit_message_text(
            _build_step_amount_min(flt, "Введите положительное число (например: 500 или 500.50)"),
            chat_id=chat_id, message_id=data["msg_id"], reply_markup=step_input_kb(),
        )
        return

    await state.update_data(pending_min=str(value))
    data = await state.get_data()
    await bot.edit_message_text(_build_step_amount_max(value), chat_id=chat_id, message_id=data["msg_id"], reply_markup=step_input_kb(),
    )
    await state.set_state(EditFilter.amount_max)


@router.message(EditFilter.amount_max)
async def receive_amount_max(
    message: Message,
    bot: Bot,
    user: User,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    chat_id = message.chat.id
    raw = (message.text or "").strip()
    try:
        await bot.delete_message(chat_id, message.message_id)
    except Exception:  # noqa: BLE001
        pass

    value = _parse_decimal_positive(raw)
    data = await state.get_data()
    pending_min_str = data.get("pending_min")
    pending_min = Decimal(pending_min_str) if pending_min_str else None

    if value is None:
        await bot.edit_message_text(_build_step_amount_max(pending_min, "Введите положительное число"), chat_id=chat_id, message_id=data["msg_id"], reply_markup=step_input_kb(),
        )
        return

    if pending_min is not None and value < pending_min:
        await bot.edit_message_text(_build_step_amount_max(pending_min, "Максимум должен быть ≥ минимума"), chat_id=chat_id, message_id=data["msg_id"], reply_markup=step_input_kb(),
        )
        return

    await FilterRepo(session).update(
        data["filter_id"], user.id, min_amount=pending_min, max_amount=value
    )
    await session.commit()
    await state.set_state(EditFilter.main)
    flt = await _load_filter(session, user, state)
    await _edit_main(bot, chat_id, data["msg_id"], flt)


# ─── Group: price range (2-step) ─────────────────────────────────────


def _build_step_price_min(flt: Filter, error: str | None = None) -> str:
    prefix = ERROR_PREFIX.format(error=error) if error else ""
    return (
        prefix
        + "📊 <b>Диапазон курса</b>\n\n"
        + f"Текущее: {flt.min_price or '—'} – {flt.max_price or '—'} {flt.currency_id}\n\n"
        + "Введите <b>минимальный</b> курс (число) "
        + "или нажмите Пропустить."
    )


def _build_step_price_max(pending_min: Decimal | None, error: str | None = None) -> str:
    prefix = ERROR_PREFIX.format(error=error) if error else ""
    min_text = str(pending_min) if pending_min is not None else "не задан"
    return (
        prefix
        + "📊 <b>Диапазон курса</b>\n\n"
        + f"Минимум: {min_text} ✅\n\n"
        + "Введите <b>максимальный</b> курс или нажмите Пропустить."
    )


@router.callback_query(F.data == "edit:group:price", EditFilter.main)
async def group_price(
    callback: CallbackQuery,
    bot: Bot,
    user: User,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    flt = await _load_filter(session, user, state)
    data = await state.get_data()
    await bot.edit_message_text(_build_step_price_min(flt), chat_id=callback.message.chat.id, message_id=data["msg_id"], reply_markup=step_input_kb(),
    )
    await state.set_state(EditFilter.price_min)
    await callback.answer()


@router.message(EditFilter.price_min)
async def receive_price_min(
    message: Message, bot: Bot, user: User, session: AsyncSession, state: FSMContext,
) -> None:
    chat_id = message.chat.id
    raw = (message.text or "").strip()
    try:
        await bot.delete_message(chat_id, message.message_id)
    except Exception:  # noqa: BLE001
        pass
    value = _parse_decimal_positive(raw)
    if value is None:
        flt = await _load_filter(session, user, state)
        data = await state.get_data()
        await bot.edit_message_text(_build_step_price_min(flt, "Введите положительное число"), chat_id=chat_id, message_id=data["msg_id"], reply_markup=step_input_kb(),
        )
        return
    await state.update_data(pending_min=str(value))
    data = await state.get_data()
    await bot.edit_message_text(_build_step_price_max(value), chat_id=chat_id, message_id=data["msg_id"], reply_markup=step_input_kb(),
    )
    await state.set_state(EditFilter.price_max)


@router.message(EditFilter.price_max)
async def receive_price_max(
    message: Message, bot: Bot, user: User, session: AsyncSession, state: FSMContext,
) -> None:
    chat_id = message.chat.id
    raw = (message.text or "").strip()
    try:
        await bot.delete_message(chat_id, message.message_id)
    except Exception:  # noqa: BLE001
        pass
    value = _parse_decimal_positive(raw)
    data = await state.get_data()
    pending_min = Decimal(data["pending_min"]) if data.get("pending_min") else None
    if value is None:
        await bot.edit_message_text(_build_step_price_max(pending_min, "Введите положительное число"), chat_id=chat_id, message_id=data["msg_id"], reply_markup=step_input_kb(),
        )
        return
    if pending_min is not None and value < pending_min:
        await bot.edit_message_text(_build_step_price_max(pending_min, "Максимум должен быть ≥ минимума"), chat_id=chat_id, message_id=data["msg_id"], reply_markup=step_input_kb(),
        )
        return
    await FilterRepo(session).update(
        data["filter_id"], user.id, min_price=pending_min, max_price=value
    )
    await session.commit()
    await state.set_state(EditFilter.main)
    flt = await _load_filter(session, user, state)
    await _edit_main(bot, chat_id, data["msg_id"], flt)


# ─── Group: experience ───────────────────────────────────────────────


def _build_experience_screen(flt: Filter) -> str:
    return (
        "👤 <b>Опыт и репутация продавца</b>\n\n"
        f"Мин. число завершённых сделок: <b>{flt.min_trades_count if flt.min_trades_count is not None else '—'}</b>\n"
        f"Мин. Completion Rate: <b>{flt.min_completion_rate if flt.min_completion_rate is not None else '—'}%</b>"
    )


@router.callback_query(F.data == "edit:group:experience", EditFilter.main)
async def group_experience(
    callback: CallbackQuery, bot: Bot, user: User, session: AsyncSession, state: FSMContext,
) -> None:
    flt = await _load_filter(session, user, state)
    data = await state.get_data()
    await bot.edit_message_text(_build_experience_screen(flt), chat_id=callback.message.chat.id, message_id=data["msg_id"], reply_markup=experience_kb(),
    )
    await state.set_state(EditFilter.experience)
    await callback.answer()


@router.callback_query(F.data == "edit:input:trades", EditFilter.experience)
async def input_trades(
    callback: CallbackQuery, bot: Bot, state: FSMContext,
) -> None:
    data = await state.get_data()
    text = (
        "👤 <b>Минимальное число сделок</b>\n\n"
        "Введите целое число ≥ 0 (или Пропустить, чтобы убрать ограничение)."
    )
    await bot.edit_message_text(text, chat_id=callback.message.chat.id, message_id=data["msg_id"], reply_markup=step_input_kb())
    await state.set_state(EditFilter.min_trades)
    await callback.answer()


@router.message(EditFilter.min_trades)
async def receive_trades(
    message: Message, bot: Bot, user: User, session: AsyncSession, state: FSMContext,
) -> None:
    chat_id = message.chat.id
    raw = (message.text or "").strip()
    try:
        await bot.delete_message(chat_id, message.message_id)
    except Exception:  # noqa: BLE001
        pass
    try:
        value = int(raw)
        if value < 0:
            raise ValueError
    except ValueError:
        data = await state.get_data()
        text = (
            "👤 <b>Минимальное число сделок</b>\n\n"
            + ERROR_PREFIX.format(error="Введите целое число ≥ 0")
            + "или Пропустить."
        )
        await bot.edit_message_text(text, chat_id=chat_id, message_id=data["msg_id"], reply_markup=step_input_kb())
        return
    data = await state.get_data()
    await FilterRepo(session).update(data["filter_id"], user.id, min_trades_count=value)
    await session.commit()
    flt = await _load_filter(session, user, state)
    await bot.edit_message_text(_build_experience_screen(flt), chat_id=chat_id, message_id=data["msg_id"], reply_markup=experience_kb(),
    )
    await state.set_state(EditFilter.experience)


@router.callback_query(F.data == "edit:input:rate", EditFilter.experience)
async def input_rate(
    callback: CallbackQuery, bot: Bot, state: FSMContext,
) -> None:
    data = await state.get_data()
    text = (
        "⭐ <b>Минимальный Completion Rate</b>\n\n"
        "Введите число от 0 до 100 (можно дробное, например 95.5) или Пропустить."
    )
    await bot.edit_message_text(text, chat_id=callback.message.chat.id, message_id=data["msg_id"], reply_markup=step_input_kb())
    await state.set_state(EditFilter.min_rate)
    await callback.answer()


@router.message(EditFilter.min_rate)
async def receive_rate(
    message: Message, bot: Bot, user: User, session: AsyncSession, state: FSMContext,
) -> None:
    chat_id = message.chat.id
    raw = (message.text or "").strip()
    try:
        await bot.delete_message(chat_id, message.message_id)
    except Exception:  # noqa: BLE001
        pass
    try:
        value = Decimal(raw.replace(",", "."))
        if not (0 <= value <= 100):
            raise InvalidOperation
    except InvalidOperation:
        data = await state.get_data()
        text = (
            "⭐ <b>Минимальный Completion Rate</b>\n\n"
            + ERROR_PREFIX.format(error="Введите число от 0 до 100")
            + "или Пропустить."
        )
        await bot.edit_message_text(text, chat_id=chat_id, message_id=data["msg_id"], reply_markup=step_input_kb())
        return
    data = await state.get_data()
    await FilterRepo(session).update(data["filter_id"], user.id, min_completion_rate=value)
    await session.commit()
    flt = await _load_filter(session, user, state)
    await bot.edit_message_text(_build_experience_screen(flt), chat_id=chat_id, message_id=data["msg_id"], reply_markup=experience_kb(),
    )
    await state.set_state(EditFilter.experience)


# ─── Group: description ──────────────────────────────────────────────


def _build_description_screen(flt: Filter) -> str:
    show = "показывать" if flt.show_no_description else "скрывать"
    wl = ", ".join(flt.whitelist_words) if flt.whitelist_words else "—"
    bl = ", ".join(flt.blacklist_words) if flt.blacklist_words else "—"
    return (
        "📝 <b>Фильтр по описанию</b>\n\n"
        f"Без описания: <b>{show}</b>\n"
        f"Whitelist: <b>{wl}</b>\n"
        f"Blacklist: <b>{bl}</b>"
    )


@router.callback_query(F.data == "edit:group:description", EditFilter.main)
async def group_description(
    callback: CallbackQuery, bot: Bot, user: User, session: AsyncSession, state: FSMContext,
) -> None:
    flt = await _load_filter(session, user, state)
    data = await state.get_data()
    await bot.edit_message_text(_build_description_screen(flt), chat_id=callback.message.chat.id, message_id=data["msg_id"], reply_markup=description_kb(flt.show_no_description),
    )
    await state.set_state(EditFilter.description)
    await callback.answer()


@router.callback_query(F.data == "edit:toggle:desc", EditFilter.description)
async def toggle_no_description(
    callback: CallbackQuery, bot: Bot, user: User, session: AsyncSession, state: FSMContext,
) -> None:
    flt = await _load_filter(session, user, state)
    new_value = not flt.show_no_description
    data = await state.get_data()
    await FilterRepo(session).update(data["filter_id"], user.id, show_no_description=new_value)
    await session.commit()
    flt = await _load_filter(session, user, state)
    await bot.edit_message_text(_build_description_screen(flt), chat_id=callback.message.chat.id, message_id=data["msg_id"], reply_markup=description_kb(flt.show_no_description),
    )
    await callback.answer()


def _parse_words(raw: str) -> list[str] | None:
    """Parse comma-separated words. Returns None for invalid (too many / too long)."""
    parts = [w.strip() for w in raw.split(",")]
    parts = [w for w in parts if w]
    if len(parts) > 32:
        return None
    if any(len(w) > 32 for w in parts):
        return None
    return parts


@router.callback_query(F.data == "edit:input:whitelist", EditFilter.description)
async def input_whitelist(callback: CallbackQuery, bot: Bot, state: FSMContext) -> None:
    data = await state.get_data()
    text = (
        "✅ <b>Whitelist слов</b>\n\n"
        "Введите слова через запятую (макс. 32 шт., каждое до 32 символов). "
        "Полностью заменит текущий список. "
        "Пустая строка = очистить. Или Пропустить."
    )
    await bot.edit_message_text(text, chat_id=callback.message.chat.id, message_id=data["msg_id"], reply_markup=step_input_kb())
    await state.set_state(EditFilter.whitelist)
    await callback.answer()


@router.callback_query(F.data == "edit:input:blacklist", EditFilter.description)
async def input_blacklist(callback: CallbackQuery, bot: Bot, state: FSMContext) -> None:
    data = await state.get_data()
    text = (
        "🚫 <b>Blacklist слов</b>\n\n"
        "Введите слова через запятую (макс. 32 шт., каждое до 32 символов). "
        "Полностью заменит текущий список. "
        "Пустая строка = очистить. Или Пропустить."
    )
    await bot.edit_message_text(text, chat_id=callback.message.chat.id, message_id=data["msg_id"], reply_markup=step_input_kb())
    await state.set_state(EditFilter.blacklist)
    await callback.answer()


async def _save_words_and_return(
    field: str,
    message: Message,
    bot: Bot,
    user: User,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    chat_id = message.chat.id
    raw = message.text or ""
    try:
        await bot.delete_message(chat_id, message.message_id)
    except Exception:  # noqa: BLE001
        pass
    words = _parse_words(raw)
    if words is None:
        data = await state.get_data()
        text = (
            f"<b>{field}</b>\n\n"
            + ERROR_PREFIX.format(error="Слишком много слов или слово > 32 символов")
            + "Введите слова через запятую или Пропустить."
        )
        await bot.edit_message_text(text, chat_id=chat_id, message_id=data["msg_id"], reply_markup=step_input_kb())
        return
    data = await state.get_data()
    field_name = "whitelist_words" if "Whitelist" in field else "blacklist_words"
    await FilterRepo(session).update(
        data["filter_id"], user.id, **{field_name: words if words else None}
    )
    await session.commit()
    flt = await _load_filter(session, user, state)
    await bot.edit_message_text(_build_description_screen(flt), chat_id=chat_id, message_id=data["msg_id"], reply_markup=description_kb(flt.show_no_description),
    )
    await state.set_state(EditFilter.description)


@router.message(EditFilter.whitelist)
async def receive_whitelist(message, bot, user, session, state):
    await _save_words_and_return("Whitelist", message, bot, user, session, state)


@router.message(EditFilter.blacklist)
async def receive_blacklist(message, bot, user, session, state):
    await _save_words_and_return("Blacklist", message, bot, user, session, state)


# ─── Group: sort & count ─────────────────────────────────────────────


def _build_sort_screen(flt: Filter) -> str:
    arrow = "↑" if flt.sort_direction == "ASC" else "↓"
    return (
        "🔃 <b>Сортировка / количество / интервал</b>\n\n"
        f"Сортировка: <b>по курсу {arrow}</b>\n"
        f"Выводить: <b>{flt.orders_count}</b>\n"
        f"Интервал обновления: <b>{flt.refresh_interval_seconds} сек</b>"
    )


@router.callback_query(F.data == "edit:group:sort", EditFilter.main)
async def group_sort(
    callback: CallbackQuery, bot: Bot, user: User, session: AsyncSession, state: FSMContext,
) -> None:
    flt = await _load_filter(session, user, state)
    data = await state.get_data()
    await bot.edit_message_text(_build_sort_screen(flt), chat_id=callback.message.chat.id, message_id=data["msg_id"], reply_markup=sort_kb(flt.sort_direction),
    )
    await state.set_state(EditFilter.sort)
    await callback.answer()


@router.callback_query(F.data.startswith("edit:sort:"), EditFilter.sort)
async def set_sort_direction(
    callback: CallbackQuery, bot: Bot, user: User, session: AsyncSession, state: FSMContext,
) -> None:
    direction = callback.data.split(":")[2]
    if direction not in ("ASC", "DESC"):
        await callback.answer("Некорректное направление", show_alert=True)
        return
    data = await state.get_data()
    await FilterRepo(session).update(data["filter_id"], user.id, sort_direction=direction)
    await session.commit()
    flt = await _load_filter(session, user, state)
    await bot.edit_message_text(_build_sort_screen(flt), chat_id=callback.message.chat.id, message_id=data["msg_id"], reply_markup=sort_kb(flt.sort_direction),
    )
    await callback.answer()


@router.callback_query(F.data == "edit:input:count", EditFilter.sort)
async def input_count(callback: CallbackQuery, bot: Bot, state: FSMContext) -> None:
    data = await state.get_data()
    text = (
        "🔢 <b>Количество ордеров</b>\n\n"
        "Введите целое число от 1 до 5 или Пропустить."
    )
    await bot.edit_message_text(text, chat_id=callback.message.chat.id, message_id=data["msg_id"], reply_markup=step_input_kb())
    await state.set_state(EditFilter.orders_count)
    await callback.answer()


@router.message(EditFilter.orders_count)
async def receive_count(
    message: Message, bot: Bot, user: User, session: AsyncSession, state: FSMContext,
) -> None:
    chat_id = message.chat.id
    raw = (message.text or "").strip()
    try:
        await bot.delete_message(chat_id, message.message_id)
    except Exception:  # noqa: BLE001
        pass
    try:
        value = int(raw)
        if not (1 <= value <= 5):
            raise ValueError
    except ValueError:
        data = await state.get_data()
        text = (
            "🔢 <b>Количество ордеров</b>\n\n"
            + ERROR_PREFIX.format(error="Целое число от 1 до 5")
            + "или Пропустить."
        )
        await bot.edit_message_text(text, chat_id=chat_id, message_id=data["msg_id"], reply_markup=step_input_kb())
        return
    data = await state.get_data()
    await FilterRepo(session).update(data["filter_id"], user.id, orders_count=value)
    await session.commit()
    flt = await _load_filter(session, user, state)
    await bot.edit_message_text(_build_sort_screen(flt), chat_id=chat_id, message_id=data["msg_id"], reply_markup=sort_kb(flt.sort_direction),
    )
    await state.set_state(EditFilter.sort)


@router.callback_query(F.data == "edit:input:interval", EditFilter.sort)
async def input_interval(callback: CallbackQuery, bot: Bot, state: FSMContext) -> None:
    data = await state.get_data()
    text = (
        "🔄 <b>Интервал обновления</b>\n\n"
        "Как часто бот будет запрашивать ордера у Bybit (в секундах).\n"
        "Введите целое число от 5 до 600 или нажмите Пропустить."
    )
    await bot.edit_message_text(
        text, chat_id=callback.message.chat.id, message_id=data["msg_id"],
        reply_markup=step_input_kb(),
    )
    await state.set_state(EditFilter.refresh_interval)
    await callback.answer()


@router.message(EditFilter.refresh_interval)
async def receive_interval(
    message: Message, bot: Bot, user: User, session: AsyncSession, state: FSMContext,
) -> None:
    chat_id = message.chat.id
    raw = (message.text or "").strip()
    try:
        await bot.delete_message(chat_id, message.message_id)
    except Exception:  # noqa: BLE001
        pass
    try:
        value = int(raw)
        if not (5 <= value <= 600):
            raise ValueError
    except ValueError:
        data = await state.get_data()
        text = (
            "🔄 <b>Интервал обновления</b>\n\n"
            + ERROR_PREFIX.format(error="Целое число от 5 до 600")
            + "или Пропустить."
        )
        await bot.edit_message_text(
            text, chat_id=chat_id, message_id=data["msg_id"], reply_markup=step_input_kb(),
        )
        return
    data = await state.get_data()
    await FilterRepo(session).update(
        data["filter_id"], user.id, refresh_interval_seconds=value
    )
    await session.commit()
    flt = await _load_filter(session, user, state)
    await bot.edit_message_text(
        _build_sort_screen(flt), chat_id=chat_id, message_id=data["msg_id"],
        reply_markup=sort_kb(flt.sort_direction),
    )
    await state.set_state(EditFilter.sort)


# ─── Skip / Back (state-aware) ───────────────────────────────────────

# Skip = "set this field to None for current step" (or "skip without change" for word lists).
# Back = "abort current sub-flow, go back to main editor".

SKIP_TRANSITIONS_TO_MAIN = {
    EditFilter.amount_max,
    EditFilter.price_max,
}


@router.callback_query(F.data == "edit:skip")
async def skip_step(
    callback: CallbackQuery, bot: Bot, user: User, session: AsyncSession, state: FSMContext,
) -> None:
    current = await state.get_state()
    data = await state.get_data()
    chat_id = callback.message.chat.id
    msg_id = data["msg_id"]
    repo = FilterRepo(session)

    if current == EditFilter.amount_min.state:
        # Skip min → ask for max with min=None pending
        await state.update_data(pending_min=None)
        await bot.edit_message_text(_build_step_amount_max(None), chat_id=chat_id, message_id=msg_id, reply_markup=step_input_kb(),
        )
        await state.set_state(EditFilter.amount_max)

    elif current == EditFilter.amount_max.state:
        pending_min = Decimal(data["pending_min"]) if data.get("pending_min") else None
        await repo.update(data["filter_id"], user.id, min_amount=pending_min, max_amount=None)
        await session.commit()
        flt = await _load_filter(session, user, state)
        await _edit_main(bot, chat_id, msg_id, flt)
        await state.set_state(EditFilter.main)

    elif current == EditFilter.price_min.state:
        await state.update_data(pending_min=None)
        await bot.edit_message_text(_build_step_price_max(None), chat_id=chat_id, message_id=msg_id, reply_markup=step_input_kb(),
        )
        await state.set_state(EditFilter.price_max)

    elif current == EditFilter.price_max.state:
        pending_min = Decimal(data["pending_min"]) if data.get("pending_min") else None
        await repo.update(data["filter_id"], user.id, min_price=pending_min, max_price=None)
        await session.commit()
        flt = await _load_filter(session, user, state)
        await _edit_main(bot, chat_id, msg_id, flt)
        await state.set_state(EditFilter.main)

    elif current in (EditFilter.min_trades.state, EditFilter.min_rate.state):
        # Skip = set to None
        field = "min_trades_count" if current == EditFilter.min_trades.state else "min_completion_rate"
        await repo.update(data["filter_id"], user.id, **{field: None})
        await session.commit()
        flt = await _load_filter(session, user, state)
        await bot.edit_message_text(_build_experience_screen(flt), chat_id=chat_id, message_id=msg_id, reply_markup=experience_kb(),
        )
        await state.set_state(EditFilter.experience)

    elif current in (EditFilter.whitelist.state, EditFilter.blacklist.state):
        # Skip = no change, just go back
        flt = await _load_filter(session, user, state)
        await bot.edit_message_text(_build_description_screen(flt), chat_id=chat_id, message_id=msg_id, reply_markup=description_kb(flt.show_no_description),
        )
        await state.set_state(EditFilter.description)

    elif current in (EditFilter.orders_count.state, EditFilter.refresh_interval.state):
        # Skip = no change for these single-value inputs
        flt = await _load_filter(session, user, state)
        await bot.edit_message_text(_build_sort_screen(flt), chat_id=chat_id, message_id=msg_id, reply_markup=sort_kb(flt.sort_direction),
        )
        await state.set_state(EditFilter.sort)

    await callback.answer()


@router.callback_query(F.data == "edit:back")
async def back_step(
    callback: CallbackQuery, bot: Bot, user: User, session: AsyncSession, state: FSMContext,
) -> None:
    current = await state.get_state()
    data = await state.get_data()
    chat_id = callback.message.chat.id
    msg_id = data["msg_id"]

    # Sub-screens (experience/description/sort) → back to main
    if current in (
        EditFilter.experience.state,
        EditFilter.description.state,
        EditFilter.sort.state,
    ):
        flt = await _load_filter(session, user, state)
        await _edit_main(bot, chat_id, msg_id, flt)
        await state.set_state(EditFilter.main)

    # Inputs inside experience → back to experience screen
    elif current in (EditFilter.min_trades.state, EditFilter.min_rate.state):
        flt = await _load_filter(session, user, state)
        await bot.edit_message_text(_build_experience_screen(flt), chat_id=chat_id, message_id=msg_id, reply_markup=experience_kb(),
        )
        await state.set_state(EditFilter.experience)

    # Inputs inside description → back to description
    elif current in (EditFilter.whitelist.state, EditFilter.blacklist.state):
        flt = await _load_filter(session, user, state)
        await bot.edit_message_text(_build_description_screen(flt), chat_id=chat_id, message_id=msg_id, reply_markup=description_kb(flt.show_no_description),
        )
        await state.set_state(EditFilter.description)

    # Input inside sort → back to sort
    elif current in (EditFilter.orders_count.state, EditFilter.refresh_interval.state):
        flt = await _load_filter(session, user, state)
        await bot.edit_message_text(_build_sort_screen(flt), chat_id=chat_id, message_id=msg_id, reply_markup=sort_kb(flt.sort_direction),
        )
        await state.set_state(EditFilter.sort)

    # Top-level inputs (amount/price min or max) → main
    elif current in (
        EditFilter.amount_min.state, EditFilter.amount_max.state,
        EditFilter.price_min.state, EditFilter.price_max.state,
    ):
        flt = await _load_filter(session, user, state)
        await _edit_main(bot, chat_id, msg_id, flt)
        await state.set_state(EditFilter.main)

    await callback.answer()
