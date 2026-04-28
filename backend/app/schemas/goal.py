import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, computed_field

from app.models.goal import GoalStatus, GoalType


class GoalCreate(BaseModel):
    name: str
    target_amount: Decimal
    target_date: date
    goal_type: GoalType = GoalType.savings


class GoalRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    target_amount: float
    target_date: date
    goal_type: GoalType
    baseline_balance: float | None
    current_amount: float
    status: GoalStatus
    created_at: datetime

    @computed_field
    @property
    def progress_pct(self) -> float:
        """Progress towards target as a percentage (0-100, capped at 100)."""
        if self.target_amount <= 0:
            return 100.0
        pct = (self.current_amount / self.target_amount) * 100
        return min(round(pct, 1), 100.0)

    @computed_field
    @property
    def remaining(self) -> float:
        return max(self.target_amount - self.current_amount, 0.0)

    model_config = {"from_attributes": True}


class GoalUpdate(BaseModel):
    name: str | None = None
    target_amount: Decimal | None = None
    target_date: date | None = None
    goal_type: GoalType | None = None
    status: GoalStatus | None = None
