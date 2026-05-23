from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from services.tracking.url import build_order_url


def header_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⏹ Остановить отслеживание", callback_data="tracking:stop")],
        ]
    )


def stopped_header_kb(filter_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="▶️ Возобновить",
                callback_data=f"tracking:resume:{filter_id}",
            )],
            [InlineKeyboardButton(text="← К фильтрам", callback_data="menu:filters")],
        ]
    )


def order_kb(ad_id: str, token_id: str, currency_id: str, side: int) -> InlineKeyboardMarkup:
    # side is advertiser's: 0 = they buy (user sells), 1 = they sell (user buys)
    action_text = "💚 Купить →" if side == 1 else "💚 Продать →"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❌ Не подходит",
                    callback_data=f"order:reject:{ad_id}",
                ),
                InlineKeyboardButton(
                    text=action_text,
                    url=build_order_url(ad_id, token_id, currency_id, side),
                ),
            ]
        ]
    )
