import uuid
from datetime import date

from pydantic import BaseModel

from app.schemas.week import WeekSummary


class GoalDelta(BaseModel):
    id: uuid.UUID
    name: str
    target_amount: float
    current_amount: float
    remaining: float
    progress_pct: float
    target_date: date
    goal_type: str
    status: str


class DashboardSummary(BaseModel):
    current_balance: float
    projection: list[WeekSummary]
    goals: list[GoalDelta]
