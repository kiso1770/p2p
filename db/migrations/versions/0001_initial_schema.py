"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-30

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # users
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "last_active_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("telegram_id"),
    )
    op.create_index(
        "idx_users_telegram_id", "users", ["telegram_id"], unique=True
    )

    # filters
    op.create_table(
        "filters",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=32), nullable=False),
        sa.Column(
            "token_id",
            sa.String(length=16),
            server_default="USDT",
            nullable=False,
        ),
        sa.Column("currency_id", sa.String(length=16), nullable=False),
        sa.Column("side", sa.SmallInteger(), nullable=False),
        sa.Column("min_amount", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("max_amount", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("min_price", sa.Numeric(precision=18, scale=8), nullable=True),
        sa.Column("max_price", sa.Numeric(precision=18, scale=8), nullable=True),
        sa.Column("min_trades_count", sa.Integer(), nullable=True),
        sa.Column(
            "min_completion_rate", sa.Numeric(precision=5, scale=2), nullable=True
        ),
        sa.Column(
            "show_no_description",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "whitelist_words", postgresql.ARRAY(sa.Text()), nullable=True
        ),
        sa.Column(
            "blacklist_words", postgresql.ARRAY(sa.Text()), nullable=True
        ),
        sa.Column(
            "sort_direction",
            sa.String(length=4),
            server_default="ASC",
            nullable=False,
        ),
        sa.Column(
            "orders_count",
            sa.SmallInteger(),
            server_default="5",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "name", name="uq_filters_user_name"),
        sa.CheckConstraint("side IN (0, 1)", name="ck_filters_side"),
        sa.CheckConstraint(
            "min_completion_rate IS NULL OR min_completion_rate BETWEEN 0 AND 100",
            name="ck_filters_completion_rate",
        ),
        sa.CheckConstraint(
            "orders_count BETWEEN 1 AND 5", name="ck_filters_orders_count"
        ),
        sa.CheckConstraint(
            "sort_direction IN ('ASC', 'DESC')",
            name="ck_filters_sort_direction",
        ),
    )
    op.create_index("idx_filters_user_id", "filters", ["user_id"])

    # description_blacklist
    op.create_table(
        "description_blacklist",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("description_hash", sa.String(length=64), nullable=False),
        sa.Column("description_text", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "description_hash", name="uq_dbl_user_hash"
        ),
    )
    op.create_index(
        "idx_dbl_user_hash",
        "description_blacklist",
        ["user_id", "description_hash"],
    )

    # Trigger function + trigger for filters.updated_at
    op.execute(
        """
        CREATE OR REPLACE FUNCTION update_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_filters_updated_at
        BEFORE UPDATE ON filters
        FOR EACH ROW EXECUTE FUNCTION update_updated_at();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_filters_updated_at ON filters;")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at();")

    op.drop_index("idx_dbl_user_hash", table_name="description_blacklist")
    op.drop_table("description_blacklist")

    op.drop_index("idx_filters_user_id", table_name="filters")
    op.drop_table("filters")

    op.drop_index("idx_users_telegram_id", table_name="users")
    op.drop_table("users")
