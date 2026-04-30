from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 Мои фильтры", callback_data="menu:filters")],
            [InlineKeyboardButton(text="⚙️ Настройки", callback_data="menu:settings")],
        ]
    )
