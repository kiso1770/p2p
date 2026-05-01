from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def main_editor_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💵 Диапазон суммы", callback_data="edit:group:amount")],
            [InlineKeyboardButton(text="📊 Диапазон курса", callback_data="edit:group:price")],
            [InlineKeyboardButton(text="👤 Опыт и репутация", callback_data="edit:group:experience")],
            [InlineKeyboardButton(text="📝 Описание и слова", callback_data="edit:group:description")],
            [InlineKeyboardButton(text="🔃 Сортировка и кол-во", callback_data="edit:group:sort")],
            [InlineKeyboardButton(text="← К списку фильтров", callback_data="edit:done")],
        ]
    )


def step_input_kb() -> InlineKeyboardMarkup:
    """Keyboard shown during a single input step: Skip / Back."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⏭ Пропустить", callback_data="edit:skip"),
                InlineKeyboardButton(text="← Назад", callback_data="edit:back"),
            ]
        ]
    )


def experience_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Мин. число сделок", callback_data="edit:input:trades")],
            [InlineKeyboardButton(text="✏️ Мин. Completion Rate (%)", callback_data="edit:input:rate")],
            [InlineKeyboardButton(text="← Назад", callback_data="edit:back")],
        ]
    )


def description_kb(show_no_description: bool) -> InlineKeyboardMarkup:
    toggle_text = (
        "📝 Без описания: показывать ↔ скрывать"
        if show_no_description
        else "📝 Без описания: скрывать ↔ показывать"
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=toggle_text, callback_data="edit:toggle:desc")],
            [InlineKeyboardButton(text="✏️ Whitelist слов", callback_data="edit:input:whitelist")],
            [InlineKeyboardButton(text="✏️ Blacklist слов", callback_data="edit:input:blacklist")],
            [InlineKeyboardButton(text="← Назад", callback_data="edit:back")],
        ]
    )


def sort_kb(sort_direction: str) -> InlineKeyboardMarkup:
    asc_text = "↑ По курсу: возрастание ✓" if sort_direction == "ASC" else "↑ По курсу: возрастание"
    desc_text = "↓ По курсу: убывание ✓" if sort_direction == "DESC" else "↓ По курсу: убывание"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=asc_text, callback_data="edit:sort:ASC")],
            [InlineKeyboardButton(text=desc_text, callback_data="edit:sort:DESC")],
            [InlineKeyboardButton(text="✏️ Изменить количество (1–5)", callback_data="edit:input:count")],
            [InlineKeyboardButton(text="← Назад", callback_data="edit:back")],
        ]
    )
