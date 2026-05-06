from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def settings_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="🚫 Чёрный список описаний",
                callback_data="settings:blacklist",
            )],
            [InlineKeyboardButton(
                text="← Главное меню",
                callback_data="settings:back_to_main",
            )],
        ]
    )


def blacklist_entry_kb(entry_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="🗑 Удалить",
                callback_data=f"bl:delete:{entry_id}",
            )]
        ]
    )


def blacklist_summary_kb(has_items: bool) -> InlineKeyboardMarkup:
    rows = []
    if has_items:
        rows.append([InlineKeyboardButton(
            text="🗑 Очистить всё",
            callback_data="bl:clear_all",
        )])
    rows.append([InlineKeyboardButton(
        text="← Назад",
        callback_data="bl:back_to_settings",
    )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def clear_all_confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Да, очистить",
                    callback_data="bl:confirm_clear",
                ),
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="bl:cancel_clear",
                ),
            ]
        ]
    )


def format_blacklist_entry(index: int, description_text: str) -> str:
    text = description_text.strip()
    if len(text) > 300:
        text = text[:300] + "…"
    return f"🚫 <b>#{index}</b>\n{text}"
