from decimal import Decimal

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from db.models import Filter

CURRENCY_FLAGS = {
    "RUB": "🇷🇺", "USD": "🇺🇸", "EUR": "🇪🇺", "KZT": "🇰🇿",
    "UAH": "🇺🇦", "GBP": "🇬🇧", "TRY": "🇹🇷", "AZN": "🇦🇿",
    "UZS": "🇺🇿", "INR": "🇮🇳",
}


def filters_summary_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Создать фильтр", callback_data="filter:create")],
            [InlineKeyboardButton(text="← Главное меню", callback_data="menu:back_to_main")],
        ]
    )


def filter_actions_kb(filter_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="▶️ Старт", callback_data=f"filter:start:{filter_id}"),
                InlineKeyboardButton(text="✏️ Ред.", callback_data=f"filter:edit:{filter_id}"),
                InlineKeyboardButton(text="🗑 Удалить", callback_data=f"filter:delete:{filter_id}"),
            ],
        ]
    )


def delete_confirm_kb(filter_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"filter:confirm_delete:{filter_id}"),
                InlineKeyboardButton(text="❌ Отмена", callback_data=f"filter:cancel_delete:{filter_id}"),
            ]
        ]
    )


def _fmt_decimal(value: Decimal | None, suffix: str = "") -> str:
    if value is None:
        return "—"
    formatted = format(value.normalize(), "f").rstrip("0").rstrip(".")
    return f"{formatted}{suffix}"


def _fmt_range(lo: Decimal | None, hi: Decimal | None, suffix: str = "") -> str:
    if lo is None and hi is None:
        return "—"
    return f"{_fmt_decimal(lo)} – {_fmt_decimal(hi)}{suffix}"


def _fmt_words(words: list[str] | None) -> str:
    if not words:
        return "—"
    return ", ".join(words)


def format_filter(flt: Filter) -> str:
    flag = CURRENCY_FLAGS.get(flt.currency_id, "💱")
    side_text = "📈 Покупка" if flt.side == 0 else "📉 Продажа"
    sort_arrow = "↑" if flt.sort_direction == "ASC" else "↓"
    show_no_desc = "показывать" if flt.show_no_description else "скрывать"

    lines = [
        f"📌 <b>{flt.name}</b>",
        f"{flag} {flt.token_id}/{flt.currency_id} • {side_text}",
        "",
        f"💵 Сумма: {_fmt_range(flt.min_amount, flt.max_amount, ' USDT')}",
        f"📊 Курс: {_fmt_range(flt.min_price, flt.max_price)}",
        f"👤 Сделок: ≥{flt.min_trades_count if flt.min_trades_count is not None else '—'}",
        f"⭐ Rate: ≥{_fmt_decimal(flt.min_completion_rate, '%') if flt.min_completion_rate is not None else '—'}",
        f"📝 Без описания: {show_no_desc}",
        f"✅ Whitelist: {_fmt_words(flt.whitelist_words)}",
        f"🚫 Blacklist: {_fmt_words(flt.blacklist_words)}",
        f"🔃 Сортировка: по курсу {sort_arrow}",
        f"🔢 Выводить: {flt.orders_count}",
    ]
    return "\n".join(lines)
