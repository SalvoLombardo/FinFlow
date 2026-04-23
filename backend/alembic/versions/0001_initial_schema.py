"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-23 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    op.create_table(
        "financial_weeks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("week_end", sa.Date(), nullable=False),
        sa.Column("opening_balance", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("closing_balance", sa.Numeric(12, 2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("user_id", "week_start", name="uq_financial_weeks_user_week_start"),
    )

    op.create_table(
        "transactions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("week_id", UUID(as_uuid=True), sa.ForeignKey("financial_weeks.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "type",
            sa.Enum("income", "expense", name="transactiontype"),
            nullable=False,
        ),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("is_recurring", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("recurrence_rule", sa.String(50), nullable=True),
        sa.Column("transaction_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "goals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("target_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=False),
        sa.Column("current_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column(
            "status",
            sa.Enum("active", "achieved", "abandoned", name="goalstatus"),
            nullable=False,
            server_default="active",
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "ai_insights",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("insight_type", sa.String(50), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("model_used", sa.String(100), nullable=True),
        sa.Column("generated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default="false"),
    )

    op.create_table(
        "user_ai_settings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("ai_enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "ai_mode",
            sa.Enum("ollama", "api_key", name="aimode"),
            nullable=False,
            server_default="api_key",
        ),
        sa.Column("ai_provider", sa.String(50), nullable=True),
        sa.Column("ai_model", sa.String(100), nullable=True),
        sa.Column("api_key_enc", sa.Text(), nullable=True),
        sa.Column("ollama_url", sa.String(255), nullable=False, server_default="http://localhost:11434"),
        sa.Column("ollama_model", sa.String(100), nullable=False, server_default="llama3.2"),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("user_id", name="uq_user_ai_settings_user_id"),
    )


def downgrade() -> None:
    op.drop_table("user_ai_settings")
    op.drop_table("ai_insights")
    op.drop_table("goals")
    op.drop_table("transactions")
    op.drop_table("financial_weeks")
    op.drop_table("users")

    op.execute("DROP TYPE IF EXISTS aimode")
    op.execute("DROP TYPE IF EXISTS goalstatus")
    op.execute("DROP TYPE IF EXISTS transactiontype")
