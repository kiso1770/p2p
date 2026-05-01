"""Filter list management: view and delete (Phase 5a).

Create / edit / start are stubs that show a "coming soon" alert and will
be implemented in Phases 5b, 5c, 6 respectively.
"""
import logging

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.filters import (
    delete_confirm_kb,
    filter_actions_kb,
    filters_summary_kb,
    format_filter,
)
from bot.keyboards.main_menu import main_menu_kb
from bot.views import ViewMessages, delete_current_view
from db.models import User
from db.repositories import FilterRepo

logger = logging.getLogger(__name__)
router = Router(name=__name__)

EMPTY_TEXT = (
    "📋 <b>Мои фильтры</b>\n\n"
    "У вас пока нет фильтров. Создайте первый!"
)
SUMMARY_TEXT = "📋 <b>Мои фильтры</b>"


# ─── Reusable view renderer ──────────────────────────────────────────


async def render_filters_view(
    bot: Bot,
    chat_id: int,
    user: User,
    session: AsyncSession,
    view_messages: ViewMessages,
) -> None:
    """Render the filters list as the current view (deletes the previous one)."""
    await delete_current_view(bot, chat_id, view_messages)

    filters = await FilterRepo(session).get_all_by_user(user.id)

    new_ids: list[int] = []
    if not filters:
        sent = await bot.send_message(chat_id, EMPTY_TEXT, reply_markup=filters_summary_kb())
        new_ids.append(sent.message_id)
    else:
        for flt in filters:
            sent = await bot.send_message(
                chat_id, format_filter(flt), reply_markup=filter_actions_kb(flt.id)
            )
            new_ids.append(sent.message_id)
        summary = await bot.send_message(chat_id, SUMMARY_TEXT, reply_markup=filters_summary_kb())
        new_ids.append(summary.message_id)

    await view_messages.set(chat_id, new_ids)


# ─── Show filters list ───────────────────────────────────────────────


@router.callback_query(F.data == "menu:filters")
async def show_filters(
    callback: CallbackQuery,
    bot: Bot,
    user: User,
    session: AsyncSession,
    view_messages: ViewMessages,
) -> None:
    await render_filters_view(bot, callback.message.chat.id, user, session, view_messages)
    await callback.answer()


# ─── Back to main menu ───────────────────────────────────────────────


@router.callback_query(F.data == "menu:back_to_main")
async def back_to_main_menu(
    callback: CallbackQuery,
    bot: Bot,
    view_messages: ViewMessages,
) -> None:
    chat_id = callback.message.chat.id
    await delete_current_view(bot, chat_id, view_messages)

    sent = await bot.send_message(chat_id, "Главное меню:", reply_markup=main_menu_kb())
    await view_messages.set(chat_id, [sent.message_id])
    await callback.answer()


# ─── Delete confirmation flow ────────────────────────────────────────


@router.callback_query(F.data.startswith("filter:delete:"))
async def confirm_delete(
    callback: CallbackQuery,
    user: User,
    session: AsyncSession,
) -> None:
    filter_id = int(callback.data.split(":")[2])
    flt = await FilterRepo(session).get_by_id(filter_id, user.id)
    if flt is None:
        await callback.answer("Фильтр не найден", show_alert=True)
        return

    text = (
        f"🗑 <b>Удаление фильтра</b>\n\n"
        f"Удалить <b>{flt.name}</b>?\n"
        f"Это действие нельзя отменить."
    )
    await callback.message.edit_text(text, reply_markup=delete_confirm_kb(filter_id))
    await callback.answer()


@router.callback_query(F.data.startswith("filter:confirm_delete:"))
async def do_delete(
    callback: CallbackQuery,
    bot: Bot,
    user: User,
    session: AsyncSession,
    view_messages: ViewMessages,
) -> None:
    filter_id = int(callback.data.split(":")[2])
    repo = FilterRepo(session)

    deleted = await repo.delete(filter_id, user.id)
    if not deleted:
        await callback.answer("Фильтр не найден", show_alert=True)
        return

    chat_id = callback.message.chat.id
    msg_id = callback.message.message_id
    try:
        await bot.delete_message(chat_id, msg_id)
    except Exception:  # noqa: BLE001
        pass
    await view_messages.remove(chat_id, msg_id)

    await callback.answer("✅ Фильтр удалён")


@router.callback_query(F.data.startswith("filter:cancel_delete:"))
async def cancel_delete(
    callback: CallbackQuery,
    user: User,
    session: AsyncSession,
) -> None:
    filter_id = int(callback.data.split(":")[2])
    flt = await FilterRepo(session).get_by_id(filter_id, user.id)
    if flt is None:
        await callback.answer("Фильтр не найден", show_alert=True)
        return

    await callback.message.edit_text(
        format_filter(flt), reply_markup=filter_actions_kb(filter_id)
    )
    await callback.answer()


# ─── Stub for Phase 6 ────────────────────────────────────────────────
# (filter:create handled by wizard, filter:edit handled by edit router)


@router.callback_query(F.data.startswith("filter:start:"))
async def stub_start(callback: CallbackQuery) -> None:
    await callback.answer("▶️ Отслеживание — в разработке (Фаза 6)", show_alert=True)
