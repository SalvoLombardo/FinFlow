import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

from app.models.transaction import TransactionType


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


class ProjectedTransaction(BaseModel):
    """A recurring transaction projected into a future week (not stored in DB)."""
    id: uuid.UUID
    name: str
    amount: float
    type: TransactionType
    category: str | None
    recurrence_rule: str | None
    recurrence_end_date: date | None


class ProjectedWeekDetail(BaseModel):
    """Returned by GET /weeks/projected — full snapshot of a virtual future week."""
    week_start: date
    week_end: date
    opening_balance: float
    closing_balance: float
    total_income: float
    total_expense: float
    transactions: list[ProjectedTransaction]
