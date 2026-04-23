from datetime import datetime
from typing import Any

from pydantic import BaseModel

# Phase 3: full implementation with aiokafka + orjson


class AuditEvent(BaseModel):
    event_id: str
    user_id: str
    action: str          # e.g. "transaction.created"
    entity_type: str
    entity_id: str
    before_state: dict[str, Any] | None
    after_state: dict[str, Any]
    timestamp: datetime
    ip_address: str | None


class KafkaAuditProducer:
    async def send(self, event: AuditEvent) -> None:
        raise NotImplementedError("Implement in Phase 3")
