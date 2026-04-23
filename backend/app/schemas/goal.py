import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

from app.models.goal import GoalStatus


class GoalCreate(BaseModel):
    name: str
    target_amount: Decimal
    target_date: date
    current_amount: Decimal = Decimal("0")


class GoalRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    target_amount: Decimal
    target_date: date
    current_amount: Decimal
    status: GoalStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class GoalUpdate(BaseModel):
    name: str | None = None
    target_amount: Decimal | None = None
    target_date: date | None = None
    current_amount: Decimal | None = None
    status: GoalStatus | None = None
