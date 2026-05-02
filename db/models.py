from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True)
    username: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_active_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    filters: Mapped[list["Filter"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    description_blacklist: Mapped[list["DescriptionBlacklist"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_users_telegram_id", "telegram_id", unique=True),
    )


class Filter(Base):
    __tablename__ = "filters"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(32), nullable=False)
    token_id: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="USDT"
    )
    currency_id: Mapped[str] = mapped_column(String(16), nullable=False)
    side: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    min_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    max_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    min_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    max_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    min_trades_count: Mapped[int | None] = mapped_column(Integer)
    min_completion_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))

    show_no_description: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    whitelist_words: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    blacklist_words: Mapped[list[str] | None] = mapped_column(ARRAY(Text))

    sort_direction: Mapped[str] = mapped_column(
        String(4), nullable=False, server_default="ASC"
    )
    orders_count: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default="5"
    )
    refresh_interval_seconds: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default="15"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="filters")

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_filters_user_name"),
        CheckConstraint("side IN (0, 1)", name="ck_filters_side"),
        CheckConstraint(
            "min_completion_rate IS NULL OR min_completion_rate BETWEEN 0 AND 100",
            name="ck_filters_completion_rate",
        ),
        CheckConstraint(
            "orders_count BETWEEN 1 AND 5", name="ck_filters_orders_count"
        ),
        CheckConstraint(
            "sort_direction IN ('ASC', 'DESC')", name="ck_filters_sort_direction"
        ),
        CheckConstraint(
            "refresh_interval_seconds BETWEEN 5 AND 600",
            name="ck_filters_refresh_interval",
        ),
        Index("idx_filters_user_id", "user_id"),
    )


class DescriptionBlacklist(Base):
    __tablename__ = "description_blacklist"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    description_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    description_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="description_blacklist")

    __table_args__ = (
        UniqueConstraint(
            "user_id", "description_hash", name="uq_dbl_user_hash"
        ),
        Index("idx_dbl_user_hash", "user_id", "description_hash"),
    )
