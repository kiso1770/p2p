"""Unit tests for services.order_filter.apply_filter."""
from decimal import Decimal

from services.hashing import hash_description
from services.order_filter import apply_filter


def ids(ads):
    return [a.id for a in ads]


def test_no_constraints_returns_all_sorted_asc(sample_ads, filter_factory):
    flt = filter_factory()
    result = apply_filter(sample_ads, flt)
    prices = [a.price for a in result]
    assert prices == sorted(prices)
    assert len(result) == len(sample_ads)


def test_amount_range_overlap(sample_ads, filter_factory):
    flt = filter_factory(min_amount=Decimal("3000"), max_amount=Decimal("10000"))
    result = apply_filter(sample_ads, flt)
    for ad in result:
        assert ad.min_amount <= flt.max_amount
        assert ad.max_amount >= flt.min_amount
    assert "a4" not in ids(result)
    assert "a5" not in ids(result)


def test_price_range(sample_ads, filter_factory):
    flt = filter_factory(min_price=Decimal("93.00"), max_price=Decimal("93.40"))
    result = apply_filter(sample_ads, flt)
    assert set(ids(result)) == {"a3", "a4", "a5", "a6", "a7"}


def test_min_trades_count(sample_ads, filter_factory):
    flt = filter_factory(min_trades_count=500)
    result = apply_filter(sample_ads, flt)
    assert all(a.recent_order_num >= 500 for a in result)
    assert "a3" not in ids(result)
    assert "a5" not in ids(result)
    assert "a6" not in ids(result)


def test_min_completion_rate(sample_ads, filter_factory):
    flt = filter_factory(min_completion_rate=Decimal("95"))
    result = apply_filter(sample_ads, flt)
    assert all(a.recent_execute_rate >= 95 for a in result)
    assert "a3" not in ids(result)
    assert "a5" not in ids(result)


def test_hide_ads_without_description(sample_ads, filter_factory):
    flt = filter_factory(show_no_description=False)
    result = apply_filter(sample_ads, flt)
    assert "a3" not in ids(result)
    assert "a9" not in ids(result)


def test_show_ads_without_description(sample_ads, filter_factory):
    flt = filter_factory(show_no_description=True)
    result = apply_filter(sample_ads, flt)
    assert "a3" in ids(result)
    assert "a9" in ids(result)


def test_whitelist_case_insensitive(sample_ads, filter_factory):
    flt = filter_factory(whitelist_words=["сбп", "сбербанк"])
    result = apply_filter(sample_ads, flt)
    assert set(ids(result)) == {"a1", "a7", "a8", "a10"}


def test_blacklist_case_insensitive(sample_ads, filter_factory):
    flt = filter_factory(blacklist_words=["VIP", "скам"])
    result = apply_filter(sample_ads, flt)
    assert "a2" not in ids(result)
    assert "a6" not in ids(result)


def test_personal_blacklist_hashes(sample_ads, filter_factory):
    flt = filter_factory()
    hidden = {hash_description("СБП Тинькофф быстро")}
    result = apply_filter(sample_ads, flt, blacklist_hashes=hidden)
    assert "a1" not in ids(result)


def test_sort_desc(sample_ads, filter_factory):
    flt = filter_factory(sort_direction="DESC")
    result = apply_filter(sample_ads, flt)
    prices = [a.price for a in result]
    assert prices == sorted(prices, reverse=True)


def test_limit_truncates(sample_ads, filter_factory):
    flt = filter_factory()
    result = apply_filter(sample_ads, flt, limit=3)
    assert len(result) == 3
