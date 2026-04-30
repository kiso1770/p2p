"""Integration smoke test — real call to Bybit P2P API.

Run only when explicitly requested:
    pytest -m integration

Requires BYBIT_API_KEY and BYBIT_API_SECRET in the .env file.
"""
import pytest

from config import settings
from services.bybit_client import BybitClient
from services.bybit_models import BybitAd

pytestmark = pytest.mark.integration


async def test_get_online_ads_real_call():
    async with BybitClient(
        api_key=settings.bybit_api_key,
        api_secret=settings.bybit_api_secret,
        base_url=settings.bybit_base_url,
    ) as client:
        result = await client.get_online_ads(
            token_id="USDT", currency_id="RUB", side=0, size=5
        )

    assert result.count >= 0
    for ad in result.items:
        assert isinstance(ad, BybitAd)
        assert ad.id
        assert ad.token_id == "USDT"
        assert ad.currency_id == "RUB"
