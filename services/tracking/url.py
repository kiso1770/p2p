"""Build URLs that open a specific Bybit P2P advertisement.

We route through https://app.bybit.com/inapp which:
  * is reachable from networks that block www.bybit.com (CIS users)
  * is the same redirect page Bybit uses when sharing ads from the app
  * triggers the bybitapp:// deep link if the app is installed (via JS)
  * falls back to the regular web URL otherwise

Limitation: without Bybit's `share_id` (32-char hex, issued only when
the app explicitly shares an ad), we can only land on the list page
filtered by token + currency, not on the specific ad's detail screen.
See TODO.md for the open task.
"""
from urllib.parse import quote


def _web_url(ad_id: str, token_id: str, currency_id: str, side: int) -> str:
    action = "buy" if side == 0 else "sell"
    return (
        f"https://www.bybit.com/en-US/p2p/{action}/{token_id}/{currency_id}"
        f"?adNo={ad_id}"
    )


def build_order_url(ad_id: str, token_id: str, currency_id: str, side: int) -> str:
    web = _web_url(ad_id, token_id, currency_id, side)
    deeplink = f"bybitapp://open/route?targetUrl={web}"
    return (
        "https://app.bybit.com/inapp"
        f"?by_dp={quote(deeplink, safe='')}"
        f"&by_web_link={quote(web, safe='')}"
        "&force_redirect=false"
    )
