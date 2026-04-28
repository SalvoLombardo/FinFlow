import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class WeekSummary(BaseModel):
    """Returned by GET /weeks (list) and used for the projection view."""
    week_id: uuid.UUID | None
    week_start: date
    week_end: date
    opening_balance: float
    closing_balance: float
    total_income: float
    total_expense: float
    net: float
    is_projected: bool
    notes: str | None = None


class WeekRead(BaseModel):
    """Returned by GET /weeks/{id} — includes metadata."""
    id: uuid.UUID
    user_id: uuid.UUID
    week_start: date
    week_end: date
    opening_balance: float
    closing_balance: float | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class WeekUpdate(BaseModel):
    """Only notes are editable by the user; balance is always computed."""
    notes: str | None = None
