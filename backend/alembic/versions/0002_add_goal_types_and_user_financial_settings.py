"""add goal_type, baseline_balance, user_financial_settings

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-28 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE TYPE goaltype AS ENUM ('liquidity', 'savings')")

    op.add_column("goals", sa.Column(
        "goal_type",
        sa.Enum("liquidity", "savings", name="goaltype"),
        nullable=False,
        server_default="savings",
    ))
    op.add_column("goals", sa.Column(
        "baseline_balance",
        sa.Numeric(12, 2),
        nullable=True,
    ))

    op.create_table(
        "user_financial_settings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("initial_balance", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("initial_balance_date", sa.Date(), nullable=False, server_default=sa.text("CURRENT_DATE")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("user_id", name="uq_user_financial_settings_user_id"),
    )


def downgrade() -> None:
    op.drop_table("user_financial_settings")
    op.drop_column("goals", "baseline_balance")
    op.drop_column("goals", "goal_type")
    op.execute("DROP TYPE IF EXISTS goaltype")
