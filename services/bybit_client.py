import hashlib
import hmac
import json
import logging
import time
from typing import Any, Self

import httpx

from services.bybit_models import AdsListResult, BybitApiResponse

logger = logging.getLogger(__name__)

ONLINE_ADS_PATH = "/v5/p2p/item/online"
SERVER_TIME_PATH = "/v5/market/time"
DEFAULT_RECV_WINDOW = 5000
DEFAULT_TIMEOUT = 10.0


class BybitError(Exception):
    """Base class for any Bybit-related error."""


class BybitAuthError(BybitError):
    """HTTP 401 — bad API key or signature."""


class BybitRateLimitError(BybitError):
    """HTTP 429 — rate limit exceeded."""

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class BybitServerError(BybitError):
    """HTTP 5xx."""


class BybitTimeoutError(BybitError):
    """Request timed out."""


class BybitApiError(BybitError):
    """Non-zero retCode in the response body."""

    def __init__(self, ret_code: int, ret_msg: str) -> None:
        super().__init__(f"Bybit API error retCode={ret_code}: {ret_msg}")
        self.ret_code = ret_code
        self.ret_msg = ret_msg


class BybitClient:
    """Async HTTP client for Bybit P2P API.

    Use as an async context manager:
        async with BybitClient(...) as client:
            ads = await client.get_online_ads("USDT", "RUB", side=0)
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: str = "https://api.bybit.com",
        timeout: float = DEFAULT_TIMEOUT,
        recv_window: int = DEFAULT_RECV_WINDOW,
    ) -> None:
        self._api_key = api_key
        self._api_secret = api_secret.encode("utf-8")
        self._base_url = base_url.rstrip("/")
        self._recv_window = recv_window
        self._client = httpx.AsyncClient(base_url=self._base_url, timeout=timeout)
        # Offset between local and Bybit server clock, in milliseconds.
        # Updated lazily on first signed request.
        self._time_offset_ms: int | None = None

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    def _sign(self, timestamp: int, body: str) -> str:
        """HMAC-SHA256 over timestamp + api_key + recv_window + body."""
        payload = f"{timestamp}{self._api_key}{self._recv_window}{body}"
        return hmac.new(self._api_secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()

    async def _sync_server_time(self) -> None:
        """Compute the offset between local clock and Bybit server clock."""
        try:
            response = await self._client.get(SERVER_TIME_PATH)
            data = response.json()
            server_ms = int(data["result"]["timeNano"]) // 1_000_000
            local_ms = int(time.time() * 1000)
            self._time_offset_ms = server_ms - local_ms
            logger.debug("Bybit time offset: %s ms", self._time_offset_ms)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to sync Bybit server time: %s", exc)
            self._time_offset_ms = 0

    async def _headers(self, body: str) -> dict[str, str]:
        if self._time_offset_ms is None:
            await self._sync_server_time()
        offset = self._time_offset_ms or 0
        timestamp = int(time.time() * 1000) + offset
        return {
            "X-BAPI-API-KEY": self._api_key,
            "X-BAPI-TIMESTAMP": str(timestamp),
            "X-BAPI-RECV-WINDOW": str(self._recv_window),
            "X-BAPI-SIGN-TYPE": "2",
            "X-BAPI-SIGN": self._sign(timestamp, body),
            "Content-Type": "application/json",
        }

    async def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        body_str = json.dumps(body, separators=(",", ":"))
        headers = await self._headers(body_str)

        try:
            response = await self._client.post(path, content=body_str, headers=headers)
        except httpx.TimeoutException as exc:
            raise BybitTimeoutError(f"Request to {path} timed out") from exc
        except httpx.HTTPError as exc:
            raise BybitError(f"HTTP error: {exc}") from exc

        if response.status_code == 401:
            raise BybitAuthError(f"Authentication failed: {response.text}")
        if response.status_code == 429:
            retry_after_raw = response.headers.get("Retry-After")
            retry_after = float(retry_after_raw) if retry_after_raw else None
            raise BybitRateLimitError("Rate limit exceeded", retry_after=retry_after)
        if 500 <= response.status_code < 600:
            raise BybitServerError(f"Server error {response.status_code}: {response.text}")
        if response.status_code != 200:
            raise BybitError(f"Unexpected status {response.status_code}: {response.text}")

        return response.json()

    async def get_online_ads(
        self,
        token_id: str,
        currency_id: str,
        side: int,
        page: int = 1,
        size: int = 300,
    ) -> AdsListResult:
        """Fetch the current order book for a (token, currency, side) combination.

        Args:
            side: 0 for buy USDT, 1 for sell USDT (Bybit convention).
            size: page size, max 300 per Bybit docs.
        """
        body = {
            "tokenId": token_id,
            "currencyId": currency_id,
            "side": str(side),
            "page": str(page),
            "size": str(size),
        }
        raw = await self._post(ONLINE_ADS_PATH, body)
        envelope = BybitApiResponse.model_validate(raw)

        if envelope.ret_code != 0:
            raise BybitApiError(envelope.ret_code, envelope.ret_msg)

        return envelope.result or AdsListResult()
