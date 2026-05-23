from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Telegram
    bot_token: str

    # Bybit
    bybit_api_key: str
    bybit_api_secret: str
    bybit_base_url: str = "https://api.bybit.com"
    # P2P "Купить →" link: direct www URL usually opens the right SPA route in
    # the system browser / app; inapp wrapper often lands on a generic WebView.
    bybit_p2p_link_mode: Literal["direct", "inapp"] = "direct"
    bybit_p2p_web_host: str = "www.bybit.com"
    bybit_p2p_web_locale: str = "en-US"

    # PostgreSQL
    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str = "postgres"
    postgres_port: int = 5432

    # Redis
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_db: int = 0

    # App
    log_level: str = "INFO"

    @field_validator("bybit_p2p_web_host", mode="before")
    @classmethod
    def normalize_p2p_web_host(cls, v: object) -> object:
        if not isinstance(v, str):
            return v
        h = v.strip().lower()
        for prefix in ("https://", "http://"):
            if h.startswith(prefix):
                h = h[len(prefix) :]
        return h.split("/")[0] or "www.bybit.com"

    @field_validator("bybit_p2p_web_locale", mode="before")
    @classmethod
    def normalize_p2p_web_locale(cls, v: object) -> object:
        if not isinstance(v, str):
            return v
        return v.strip().strip("/") or "en-US"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"


settings = Settings()
