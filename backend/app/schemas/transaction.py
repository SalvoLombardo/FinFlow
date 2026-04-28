import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

from app.models.transaction import TransactionType


class TransactionCreate(BaseModel):
    name: str
    amount: Decimal
    type: TransactionType
    category: str | None = None
    is_recurring: bool = False
    recurrence_rule: str | None = None
    # The backend derives the week from this date; defaults to today if omitted.
    transaction_date: date | None = None
    notes: str | None = None


class TransactionRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    week_id: uuid.UUID
    name: str
    amount: float
    type: TransactionType
    category: str | None
    is_recurring: bool
    recurrence_rule: str | None
    transaction_date: date | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TransactionUpdate(BaseModel):
    name: str | None = None
    amount: Decimal | None = None
    type: TransactionType | None = None
    category: str | None = None
    is_recurring: bool | None = None
    recurrence_rule: str | None = None
    transaction_date: date | None = None
    notes: str | None = None
