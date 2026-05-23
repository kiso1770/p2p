"""Build URLs that open a specific Bybit P2P advertisement.

Default (**direct**): one HTTPS URL to ``www.bybit.com/{locale}/p2p/...`` with
``itemId`` + ``adNo`` (API ``id``). This avoids ``app.bybit.com/inapp``, which
often opens Telegram's WebView on a generic OTC/list shell instead of the ad
route.

Optional (**inapp**): wrap via ``https://app.bybit.com/inapp`` + ``bybitapp://``
for CIS / blocked ``www`` — see ``BYBIT_P2P_LINK_MODE`` in ``config.py``.

Official docs still do not guarantee a detail screen; see ``docs/bybit-p2p-links.md``.
"""
from urllib.parse import quote, urlencode

from config import settings


def _web_url(
    ad_id: str,
    token_id: str,
    currency_id: str,
    side: int,
    *,
    host: str,
    locale: str,
) -> str:
    # side is the advertiser's side: 0 = advertiser buys USDT (user sells),
    # 1 = advertiser sells USDT (user buys).  The web URL uses the *user's*
    # action, so it's inverted.
    action = "sell" if side == 0 else "buy"
    path = f"https://{host}/{locale}/p2p/{action}/{token_id}/{currency_id}"
    qs = urlencode({"itemId": ad_id, "adNo": ad_id})
    return f"{path}?{qs}"


def build_order_url(
    ad_id: str,
    token_id: str,
    currency_id: str,
    side: int,
    *,
    link_mode: str | None = None,
    web_locale: str | None = None,
    web_host: str | None = None,
) -> str:
    """Return Telegram ``url`` for the ad. Optional kwargs override ``settings`` (tests)."""
    mode = link_mode if link_mode is not None else settings.bybit_p2p_link_mode
    locale = web_locale if web_locale is not None else settings.bybit_p2p_web_locale
    host = web_host if web_host is not None else settings.bybit_p2p_web_host

    web = _web_url(ad_id, token_id, currency_id, side, host=host, locale=locale)
    if mode == "inapp":
        deeplink = f"bybitapp://open/route?targetUrl={quote(web, safe='')}"
        return (
            "https://app.bybit.com/inapp"
            f"?by_dp={quote(deeplink, safe='')}"
            f"&by_web_link={quote(web, safe='')}"
            "&force_redirect=false"
        )
    return web
