import asyncio
import logging
from datetime import datetime
from typing import Any
from uuid import uuid4

import orjson
from aiokafka import AIOKafkaProducer
from pydantic import BaseModel, Field

from app.core.config import settings

logger = logging.getLogger(__name__)

_MAX_ATTEMPTS = 3


class AuditEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    action: str
    entity_type: str
    entity_id: str
    before_state: dict[str, Any] | None = None
    after_state: dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    ip_address: str | None = None


class KafkaAuditProducer:
    """Publishes AuditEvents to Kafka from the FastAPI Lambda.

    Creates a new producer connection per call — safe for Lambda (ephemeral compute).
    Callers should use asyncio.create_task(producer.send(...)) for true fire-and-forget:
    retries happen in the background without adding latency to the HTTP response.
    """

    async def send(self, event: AuditEvent) -> None:
        for attempt in range(_MAX_ATTEMPTS):
            try:
                producer = AIOKafkaProducer(bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS)
                await producer.start()
                try:
                    await producer.send_and_wait(
                        settings.KAFKA_AUDIT_TOPIC,
                        value=orjson.dumps(event.model_dump(mode="json")),
                        key=event.user_id.encode(),
                    )
                finally:
                    await producer.stop()
                logger.info(
                    "AUDIT action=%s entity_type=%s entity_id=%s user=%s",
                    event.action,
                    event.entity_type,
                    event.entity_id,
                    event.user_id,
                )
                return
            except Exception as exc:
                logger.warning(
                    "Kafka audit attempt %d/%d failed: %s", attempt + 1, _MAX_ATTEMPTS, exc
                )
                if attempt < _MAX_ATTEMPTS - 1:
                    await asyncio.sleep(2**attempt)

        logger.error(
            "Kafka audit gave up after %d attempts — action=%s entity_id=%s",
            _MAX_ATTEMPTS,
            event.action,
            event.entity_id,
        )


audit_producer = KafkaAuditProducer()
