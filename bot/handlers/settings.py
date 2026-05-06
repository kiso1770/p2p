"""Settings + personal description blacklist (Phase 8)."""
import logging

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.main_menu import main_menu_kb
from bot.keyboards.settings import (
    blacklist_entry_kb,
    blacklist_summary_kb,
    clear_all_confirm_kb,
    format_blacklist_entry,
    settings_menu_kb,
)
from bot.views import ViewMessages, delete_current_view
from db.models import User
from db.repositories import BlacklistRepo

logger = logging.getLogger(__name__)
router = Router(name=__name__)


SETTINGS_TEXT = "⚙️ <b>Настройки</b>"
BLACKLIST_EMPTY_TEXT = (
    "🚫 <b>Чёрный список описаний</b>\n\n"
    "Список пуст.\n"
    "Нажмите «❌ Не подходит» у ордера во время отслеживания, "
    "чтобы добавить его описание сюда."
)
BLACKLIST_SUMMARY_TEXT = "🚫 <b>Чёрный список описаний</b>"
CLEAR_CONFIRM_TEXT = (
    "🗑 <b>Очистка чёрного списка</b>\n\n"
    "Удалить все записи? Это действие нельзя отменить."
)


# ─── Render helpers ──────────────────────────────────────────────────


async def render_settings_view(
    bot: Bot, chat_id: int, view_messages: ViewMessages,
) -> None:
    await delete_current_view(bot, chat_id, view_messages)
    sent = await bot.send_message(chat_id, SETTINGS_TEXT, reply_markup=settings_menu_kb())
    await view_messages.set(chat_id, [sent.message_id])


async def render_blacklist_view(
    bot: Bot, chat_id: int, user: User, session: AsyncSession,
    view_messages: ViewMessages,
) -> None:
    await delete_current_view(bot, chat_id, view_messages)

    entries = await BlacklistRepo(session).get_all_by_user(user.id)

    new_ids: list[int] = []
    if not entries:
        sent = await bot.send_message(
            chat_id, BLACKLIST_EMPTY_TEXT,
            reply_markup=blacklist_summary_kb(has_items=False),
        )
        new_ids.append(sent.message_id)
    else:
        for index, entry in enumerate(entries, start=1):
            sent = await bot.send_message(
                chat_id,
                format_blacklist_entry(index, entry.description_text),
                reply_markup=blacklist_entry_kb(entry.id),
            )
            new_ids.append(sent.message_id)
        summary = await bot.send_message(
            chat_id, BLACKLIST_SUMMARY_TEXT,
            reply_markup=blacklist_summary_kb(has_items=True),
        )
        new_ids.append(summary.message_id)

    await view_messages.set(chat_id, new_ids)


# ─── Settings menu ───────────────────────────────────────────────────


@router.callback_query(F.data == "menu:settings")
async def show_settings(
    callback: CallbackQuery, bot: Bot, view_messages: ViewMessages,
) -> None:
    await render_settings_view(bot, callback.message.chat.id, view_messages)
    await callback.answer()


@router.callback_query(F.data == "settings:back_to_main")
async def back_to_main(
    callback: CallbackQuery, bot: Bot, view_messages: ViewMessages,
) -> None:
    chat_id = callback.message.chat.id
    await delete_current_view(bot, chat_id, view_messages)
    sent = await bot.send_message(chat_id, "Главное меню:", reply_markup=main_menu_kb())
    await view_messages.set(chat_id, [sent.message_id])
    await callback.answer()


# ─── Blacklist ───────────────────────────────────────────────────────


@router.callback_query(F.data == "settings:blacklist")
async def show_blacklist(
    callback: CallbackQuery, bot: Bot, user: User,
    session: AsyncSession, view_messages: ViewMessages,
) -> None:
    await render_blacklist_view(
        bot, callback.message.chat.id, user, session, view_messages,
    )
    await callback.answer()


@router.callback_query(F.data == "bl:back_to_settings")
async def blacklist_back_to_settings(
    callback: CallbackQuery, bot: Bot, view_messages: ViewMessages,
) -> None:
    await render_settings_view(bot, callback.message.chat.id, view_messages)
    await callback.answer()


@router.callback_query(F.data.startswith("bl:delete:"))
async def delete_blacklist_entry(
    callback: CallbackQuery, bot: Bot, user: User,
    session: AsyncSession, view_messages: ViewMessages,
) -> None:
    entry_id = int(callback.data.split(":")[2])
    repo = BlacklistRepo(session)

    deleted = await repo.delete_by_id(entry_id, user.id)
    if not deleted:
        await callback.answer("Запись не найдена", show_alert=True)
        return

    chat_id = callback.message.chat.id
    msg_id = callback.message.message_id
    try:
        await bot.delete_message(chat_id, msg_id)
    except Exception:  # noqa: BLE001
        pass
    await view_messages.remove(chat_id, msg_id)

    await callback.answer("Удалено")


@router.callback_query(F.data == "bl:clear_all")
async def clear_all_prompt(callback: CallbackQuery) -> None:
    try:
        await callback.message.edit_text(
            CLEAR_CONFIRM_TEXT, reply_markup=clear_all_confirm_kb(),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("edit failed: %s", exc)
    await callback.answer()


@router.callback_query(F.data == "bl:cancel_clear")
async def cancel_clear(callback: CallbackQuery) -> None:
    try:
        await callback.message.edit_text(
            BLACKLIST_SUMMARY_TEXT,
            reply_markup=blacklist_summary_kb(has_items=True),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("edit failed: %s", exc)
    await callback.answer()


@router.callback_query(F.data == "bl:confirm_clear")
async def confirm_clear(
    callback: CallbackQuery, bot: Bot, user: User,
    session: AsyncSession, view_messages: ViewMessages,
) -> None:
    repo = BlacklistRepo(session)
    deleted_count = await repo.delete_all_by_user(user.id)

    # Re-render the blacklist view (now empty) — handles message cleanup
    await render_blacklist_view(
        bot, callback.message.chat.id, user, session, view_messages,
    )
    await callback.answer(f"Удалено записей: {deleted_count}")
