from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from services.tracking.url import build_order_url


def header_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⏹ Остановить отслеживание", callback_data="tracking:stop")],
        ]
    )


def stopped_header_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="← К фильтрам", callback_data="menu:filters")],
        ]
    )


def order_kb(ad_id: str, token_id: str, currency_id: str, side: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❌ Не подходит",
                    callback_data=f"order:reject:{ad_id}",
                ),
                InlineKeyboardButton(
                    text="💚 Купить →",
                    url=build_order_url(ad_id, token_id, currency_id, side),
                ),
            ]
        ]
    )
