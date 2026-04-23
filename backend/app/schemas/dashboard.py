import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class WeekProjection(BaseModel):
    week_id: uuid.UUID | None
    week_start: date
    projected_balance: Decimal


class GoalDelta(BaseModel):
    id: uuid.UUID
    name: str
    target_amount: Decimal
    current_amount: Decimal
    remaining: Decimal
    target_date: date
    status: str


class DashboardSummary(BaseModel):
    current_balance: Decimal
    projection: list[WeekProjection]
    goals: list[GoalDelta]
