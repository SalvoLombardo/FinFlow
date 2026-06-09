import asyncio
import logging
import os
from datetime import datetime
from typing import Any
from uuid import uuid4

import boto3
import orjson
from aiokafka import AIOKafkaProducer
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_AUDIT_TOPIC = os.environ.get("KAFKA_AUDIT_TOPIC", "finflow.audit")
_AWS_REGION = os.environ.get("AWS_REGION", "eu-west-1")

_MAX_ATTEMPTS = 3
_CW_NAMESPACE = "FinFlow/Audit"
_CW_METRIC_DROPPED = "DroppedAuditEvents"


def _emit_drop_metric(action: str) -> None:
    """Push a single Count=1 data point to CloudWatch when an audit event is permanently dropped.

    Swallows any emission failure — dropping a metric must never raise in the caller.
    """
    try:
        cw = boto3.client("cloudwatch", region_name=_AWS_REGION)
        cw.put_metric_data(
            Namespace=_CW_NAMESPACE,
            MetricData=[{
                "MetricName": _CW_METRIC_DROPPED,
                "Value": 1,
                "Unit": "Count",
                "Dimensions": [{"Name": "Action", "Value": action}],
            }],
        )
    except Exception as exc:
        logger.warning("Failed to emit Kafka drop metric: %s", exc)


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
    """Publishes AuditEvents to Kafka.

    Creates a new producer connection per call — safe for both Lambda (ephemeral)
    and Celery (long-running) contexts. Fire-and-forget: never raises.
    """

    async def send(self, event: AuditEvent) -> None:
        for attempt in range(_MAX_ATTEMPTS):
            try:
                producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS)
                await producer.start()
                try:
                    await producer.send_and_wait(
                        KAFKA_AUDIT_TOPIC,
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
        _emit_drop_metric(event.action)


audit_producer = KafkaAuditProducer()
