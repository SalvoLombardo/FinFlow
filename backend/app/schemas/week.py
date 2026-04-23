import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class WeekCreate(BaseModel):
    week_start: date
    week_end: date
    opening_balance: Decimal = Decimal("0")
    notes: str | None = None


class WeekRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    week_start: date
    week_end: date
    opening_balance: Decimal
    closing_balance: Decimal | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class WeekUpdate(BaseModel):
    closing_balance: Decimal | None = None
    notes: str | None = None
