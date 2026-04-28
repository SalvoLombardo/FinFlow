import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class GoalStatus(str, enum.Enum):
    active = "active"
    achieved = "achieved"
    abandoned = "abandoned"


class GoalType(str, enum.Enum):
    liquidity = "liquidity"
    savings = "savings"


class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    target_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    target_date: Mapped[date] = mapped_column(Date, nullable=False)
    goal_type: Mapped[GoalType] = mapped_column(Enum(GoalType), nullable=False, default=GoalType.savings)
    # For savings goals: balance snapshot at creation time (delta reference).
    # For liquidity goals: None (progress is measured against projected balance).
    baseline_balance: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    # Cached computed value updated by projection_consumer Lambda.
    current_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    status: Mapped[GoalStatus] = mapped_column(Enum(GoalStatus), default=GoalStatus.active)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), default=datetime.utcnow)
