"""Golden test for HMAC-SHA256 signature.

Reference values are computed manually with the official Bybit V5 formula:
    sign = HMAC_SHA256(api_secret, f"{timestamp}{api_key}{recv_window}{body}")
"""
import hashlib
import hmac

from services.bybit_client import BybitClient


def _expected_sign(api_secret: str, timestamp: int, api_key: str, recv_window: int, body: str) -> str:
    payload = f"{timestamp}{api_key}{recv_window}{body}".encode("utf-8")
    return hmac.new(api_secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def test_sign_matches_reference_implementation():
    api_key = "TEST_KEY"
    api_secret = "TEST_SECRET"
    timestamp = 1700000000000
    recv_window = 5000
    body = '{"tokenId":"USDT","currencyId":"RUB","side":"0","page":"1","size":"10"}'

    client = BybitClient(api_key=api_key, api_secret=api_secret, recv_window=recv_window)
    try:
        actual = client._sign(timestamp, body)
        expected = _expected_sign(api_secret, timestamp, api_key, recv_window, body)
        assert actual == expected
        # Hex-encoded SHA-256 has 64 chars
        assert len(actual) == 64
    finally:
        # Close the underlying http client
        import asyncio
        asyncio.run(client.close())


def test_sign_changes_when_body_changes():
    client = BybitClient(api_key="K", api_secret="S")
    try:
        sig_a = client._sign(1700000000000, '{"a":1}')
        sig_b = client._sign(1700000000000, '{"a":2}')
        assert sig_a != sig_b
    finally:
        import asyncio
        asyncio.run(client.close())
