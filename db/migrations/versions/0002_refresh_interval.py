"""add refresh_interval_seconds to filters

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-01

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "filters",
        sa.Column(
            "refresh_interval_seconds",
            sa.SmallInteger(),
            server_default="15",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_filters_refresh_interval",
        "filters",
        "refresh_interval_seconds BETWEEN 5 AND 600",
    )


def downgrade() -> None:
    op.drop_constraint("ck_filters_refresh_interval", "filters", type_="check")
    op.drop_column("filters", "refresh_interval_seconds")
