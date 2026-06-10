"""add source_event_id to ai_insights for SQS idempotency

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-10 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ai_insights",
        sa.Column("source_event_id", sa.String(length=64), nullable=True),
    )
    op.create_unique_constraint(
        "uq_ai_insights_user_source_event",
        "ai_insights",
        ["user_id", "source_event_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_ai_insights_user_source_event", "ai_insights", type_="unique"
    )
    op.drop_column("ai_insights", "source_event_id")
