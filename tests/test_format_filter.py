"""Tests for filter formatting in bot.keyboards.filters.format_filter."""
from decimal import Decimal
from types import SimpleNamespace

from bot.keyboards.filters import format_filter


def _flt(**overrides):
    defaults = dict(
        name="X",
        token_id="USDT",
        currency_id="RUB",
        side=0,
        min_amount=None,
        max_amount=None,
        min_price=None,
        max_price=None,
        min_trades_count=None,
        min_completion_rate=None,
        show_no_description=True,
        whitelist_words=None,
        blacklist_words=None,
        sort_direction="ASC",
        orders_count=5,
        refresh_interval_seconds=15,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_integer_amounts_render_correctly():
    text = format_filter(_flt(min_amount=Decimal("10"), max_amount=Decimal("100")))
    assert "10 – 100" in text
    assert "1 – 1" not in text


def test_integer_prices_render_correctly():
    text = format_filter(_flt(min_price=Decimal("145"), max_price=Decimal("180")))
    assert "145 – 180" in text


def test_decimal_amounts_strip_trailing_zeros_only_after_dot():
    text = format_filter(_flt(min_amount=Decimal("10.50"), max_amount=Decimal("100.00")))
    assert "10.5 – 100" in text


def test_unset_amounts_show_dash():
    text = format_filter(_flt())
    assert "Сумма: —" in text
    assert "Курс: —" in text


def test_completion_rate_with_decimals():
    text = format_filter(_flt(min_completion_rate=Decimal("95.5")))
    assert "95.5%" in text


def test_completion_rate_integer():
    text = format_filter(_flt(min_completion_rate=Decimal("90")))
    assert "≥90%" in text
    assert "≥9%" not in text


def test_min_trades_count_integer():
    text = format_filter(_flt(min_trades_count=100))
    assert "≥100" in text


def test_orders_count_displayed():
    text = format_filter(_flt(orders_count=3))
    assert "Выводить: 3" in text


def test_refresh_interval_default():
    text = format_filter(_flt())
    assert "Интервал: 15 сек" in text


def test_refresh_interval_custom():
    text = format_filter(_flt(refresh_interval_seconds=60))
    assert "Интервал: 60 сек" in text


def test_whitelist_and_blacklist_render():
    text = format_filter(_flt(
        whitelist_words=["СБП", "Тинькофф"],
        blacklist_words=["VIP"],
    ))
    assert "Whitelist: СБП, Тинькофф" in text
    assert "Blacklist: VIP" in text
