from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class BybitAd(BaseModel):
    """A single P2P advertisement returned by /v5/p2p/item/online."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: str = Field(description="Ad ID, used for the order URL on Bybit")
    account_id: str = Field(alias="accountId", default="")
    nick_name: str = Field(alias="nickName", default="")
    token_id: str = Field(alias="tokenId")
    currency_id: str = Field(alias="currencyId")
    side: int = Field(description="0 = buy USDT, 1 = sell USDT")
    price: Decimal
    last_quantity: Decimal = Field(
        alias="lastQuantity",
        description="Currently available token amount",
    )
    min_amount: Decimal = Field(alias="minAmount")
    max_amount: Decimal = Field(alias="maxAmount")
    remark: str | None = Field(default=None, description="Free-text description / terms")
    recent_order_num: int = Field(alias="recentOrderNum", default=0)
    recent_execute_rate: int = Field(
        alias="recentExecuteRate",
        default=0,
        description="Completion rate over the last 30 days, %",
    )
    trade_count: int = Field(alias="tradeCount", default=0)
    auth_tag: list[str] = Field(alias="authTag", default_factory=list)
    is_online: bool = Field(alias="isOnline", default=True)
    payments: list[str] = Field(default_factory=list)


class AdsListResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    count: int = 0
    items: list[BybitAd] = Field(default_factory=list)


class BybitApiResponse(BaseModel):
    """Envelope used by Bybit P2P endpoints (note: snake_case fields)."""

    model_config = ConfigDict(extra="ignore")

    ret_code: int
    ret_msg: str = ""
    result: AdsListResult | None = None
