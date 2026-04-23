from datetime import datetime
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field


class EventType(str, Enum):
    BUDGET_UPDATED = "budget.updated"
    WEEK_CLOSED = "week.closed"
    GOAL_PROGRESS = "goal.progress"
    AI_ANALYSIS_REQUESTED = "ai.analysis.requested"


class FinFlowEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: EventType
    user_id: str
    payload: dict
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source: str = "finflow-api"
