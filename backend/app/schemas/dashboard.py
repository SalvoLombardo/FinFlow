import uuid
from datetime import date

from pydantic import BaseModel


class WeekProjection(BaseModel):
    week_id: uuid.UUID | None
    week_start: date
    projected_balance: float


class GoalDelta(BaseModel):
    id: uuid.UUID
    name: str
    target_amount: float
    current_amount: float
    remaining: float
    target_date: date
    status: str


class DashboardSummary(BaseModel):
    current_balance: float
    projection: list[WeekProjection]
    goals: list[GoalDelta]
