import sys
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
import pytest_asyncio
import redis.asyncio as aioredis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import settings  # noqa: E402
from services.bybit_models import BybitAd  # noqa: E402

TEST_DATABASE_URL = (
    f"postgresql+asyncpg://{settings.postgres_user}:{settings.postgres_password}"
    f"@localhost:{settings.postgres_port}/{settings.postgres_db}"
)
TEST_REDIS_URL = f"redis://localhost:{settings.redis_port}/15"

TRUNCATE_SQL = text(
    "TRUNCATE TABLE description_blacklist, filters, users RESTART IDENTITY CASCADE"
)


def _ad(
    ad_id: str,
    price: str = "92.0",
    last_quantity: str = "10000",
    min_amount: str = "100",
    max_amount: str = "10000",
    remark: str | None = "default description",
    recent_order_num: int = 500,
    recent_execute_rate: int = 98,
    nick_name: str = "Trader",
) -> BybitAd:
    return BybitAd(
        id=ad_id,
        accountId="acc-" + ad_id,
        nickName=nick_name,
        tokenId="USDT",
        currencyId="RUB",
        side=0,
        price=Decimal(price),
        lastQuantity=Decimal(last_quantity),
        minAmount=Decimal(min_amount),
        maxAmount=Decimal(max_amount),
        remark=remark,
        recentOrderNum=recent_order_num,
        recentExecuteRate=recent_execute_rate,
    )


@pytest.fixture
def ad_factory():
    return _ad


@pytest.fixture
def sample_ads():
    """Ten ads covering a variety of prices, ranges, descriptions, reputations."""
    return [
        _ad("a1", price="92.00", min_amount="500", max_amount="50000",
            remark="СБП Тинькофф быстро", recent_order_num=1240, recent_execute_rate=99),
        _ad("a2", price="92.50", min_amount="1000", max_amount="100000",
            remark="Только VIP клиенты", recent_order_num=856, recent_execute_rate=97),
        _ad("a3", price="93.00", min_amount="100", max_amount="5000",
            remark=None, recent_order_num=50, recent_execute_rate=92),
        _ad("a4", price="93.10", min_amount="50000", max_amount="500000",
            remark="Крупные суммы", recent_order_num=3000, recent_execute_rate=100),
        _ad("a5", price="93.20", min_amount="100", max_amount="1000",
            remark="новичок", recent_order_num=5, recent_execute_rate=80),
        _ad("a6", price="93.30", min_amount="200", max_amount="20000",
            remark="скам не предлагать", recent_order_num=400, recent_execute_rate=95),
        _ad("a7", price="93.40", min_amount="500", max_amount="30000",
            remark="СБП", recent_order_num=900, recent_execute_rate=96),
        _ad("a8", price="93.50", min_amount="1500", max_amount="80000",
            remark="Сбербанк", recent_order_num=2000, recent_execute_rate=99),
        _ad("a9", price="93.60", min_amount="100", max_amount="10000",
            remark="", recent_order_num=300, recent_execute_rate=94),
        _ad("a10", price="94.00", min_amount="300", max_amount="15000",
            remark="Описание с разными словами и СБП и тинькофф",
            recent_order_num=1500, recent_execute_rate=99),
    ]


def make_filter(**overrides) -> SimpleNamespace:
    """Build a duck-typed Filter object with sensible defaults for tests.

    We use SimpleNamespace instead of the SQLAlchemy Filter model to avoid
    spinning up a DB session for unit tests of pure logic.
    """
    defaults = dict(
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
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


@pytest.fixture
def filter_factory():
    return make_filter


# ─── DB / Redis fixtures (integration) ───────────────────────────────


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as session:
            await session.execute(TRUNCATE_SQL)
            await session.commit()
            yield session
            await session.rollback()
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def redis_client():
    client = aioredis.from_url(TEST_REDIS_URL)
    await client.flushdb()
    yield client
    await client.flushdb()
    await client.aclose()
