from collections.abc import Iterable
from decimal import Decimal

from db.models import Filter
from services.bybit_models import BybitAd
from services.hashing import hash_description


def _passes(ad: BybitAd, flt: Filter, blacklist_hashes: set[str]) -> bool:
    description = (ad.remark or "").strip()
    has_description = bool(description)

    if not flt.show_no_description and not has_description:
        return False

    if has_description and hash_description(description) in blacklist_hashes:
        return False

    if flt.min_amount is not None and ad.max_amount < Decimal(flt.min_amount):
        return False
    if flt.max_amount is not None and ad.min_amount > Decimal(flt.max_amount):
        return False

    if flt.min_price is not None and ad.price < Decimal(flt.min_price):
        return False
    if flt.max_price is not None and ad.price > Decimal(flt.max_price):
        return False

    if flt.min_trades_count is not None and ad.recent_order_num < flt.min_trades_count:
        return False
    if (
        flt.min_completion_rate is not None
        and ad.recent_execute_rate < int(Decimal(flt.min_completion_rate))
    ):
        return False

    desc_lower = description.lower()
    whitelist = flt.whitelist_words or []
    if whitelist and not any(word.lower() in desc_lower for word in whitelist):
        return False

    blacklist = flt.blacklist_words or []
    if blacklist and any(word.lower() in desc_lower for word in blacklist):
        return False

    return True


def apply_filter(
    ads: Iterable[BybitAd],
    flt: Filter,
    blacklist_hashes: set[str] | None = None,
    limit: int = 15,
) -> list[BybitAd]:
    """Filter, sort and truncate the ads list according to the user's filter.

    Args:
        ads: raw ads from Bybit API.
        flt: SQLAlchemy Filter model with user's conditions.
        blacklist_hashes: set of sha256 hashes of descriptions the user has hidden.
        limit: buffer size; defaults to 15 — what the tracking engine pre-loads.

    Returns:
        List of ads, sorted by price ASC/DESC according to flt.sort_direction,
        truncated to `limit`.
    """
    blacklist_hashes = blacklist_hashes or set()
    matching = [ad for ad in ads if _passes(ad, flt, blacklist_hashes)]

    reverse = flt.sort_direction == "DESC"
    matching.sort(key=lambda a: a.price, reverse=reverse)

    return matching[:limit]
