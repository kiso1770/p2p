from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.currencies import CURRENCIES, currency_flag

CURRENCIES_PER_PAGE = 15  # 5 rows × 3 columns


def _total_pages() -> int:
    return (len(CURRENCIES) + CURRENCIES_PER_PAGE - 1) // CURRENCIES_PER_PAGE


def currency_picker_kb(page: int = 0) -> InlineKeyboardMarkup:
    total = _total_pages()
    page = max(0, min(page, total - 1))

    start = page * CURRENCIES_PER_PAGE
    chunk = CURRENCIES[start: start + CURRENCIES_PER_PAGE]

    rows: list[list[InlineKeyboardButton]] = []
    for chunk_start in range(0, len(chunk), 3):
        row = []
        for code in chunk[chunk_start: chunk_start + 3]:
            row.append(
                InlineKeyboardButton(
                    text=f"{currency_flag(code)} {code}",
                    callback_data=f"wiz:cur:{code}",
                )
            )
        rows.append(row)

    nav_row: list[InlineKeyboardButton] = []
    if page > 0:
        nav_row.append(
            InlineKeyboardButton(text="← Пред.", callback_data=f"wiz:cur_page:{page - 1}")
        )
    nav_row.append(
        InlineKeyboardButton(text=f"{page + 1}/{total}", callback_data="wiz:noop")
    )
    if page < total - 1:
        nav_row.append(
            InlineKeyboardButton(text="След. →", callback_data=f"wiz:cur_page:{page + 1}")
        )
    rows.append(nav_row)

    rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="wiz:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def side_picker_kb(currency_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=f"📈 Покупка USDT за {currency_id}",
                callback_data="wiz:side:0",
            )],
            [InlineKeyboardButton(
                text=f"📉 Продажа USDT за {currency_id}",
                callback_data="wiz:side:1",
            )],
            [
                InlineKeyboardButton(text="← Назад", callback_data="wiz:back"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="wiz:cancel"),
            ],
        ]
    )


def name_input_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="← Назад", callback_data="wiz:back"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="wiz:cancel"),
            ]
        ]
    )
