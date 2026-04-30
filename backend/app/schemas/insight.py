from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class AIInsightRead(BaseModel):
    id: UUID
    insight_type: str | None
    content: str
    model_used: str | None
    generated_at: datetime
    is_read: bool

    model_config = {"from_attributes": True}
