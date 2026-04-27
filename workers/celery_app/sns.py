import json
import logging
import time
import uuid
from datetime import datetime

import boto3
from botocore.exceptions import ClientError

from celery_app.settings import worker_settings

logger = logging.getLogger(__name__)


def publish_event(event_type: str, user_id: str, payload: dict) -> None:
    """Publish a FinFlow event to SNS synchronously.

    When AWS_SNS_TOPIC_ARN is empty (local / CI), logs the event instead.
    Never raises — fire-and-forget.
    """
    event = {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "user_id": user_id,
        "payload": payload,
        "timestamp": datetime.utcnow().isoformat(),
        "source": "finflow-workers",
    }

    if not worker_settings.AWS_SNS_TOPIC_ARN:
        logger.info(
            "SNS_LOCAL event_type=%s user_id=%s body=%s",
            event_type,
            user_id,
            json.dumps(event),
        )
        return

    client = boto3.client("sns", region_name=worker_settings.AWS_REGION)
    for attempt in range(worker_settings.MAX_SNS_ATTEMPTS):
        try:
            client.publish(
                TopicArn=worker_settings.AWS_SNS_TOPIC_ARN,
                Message=json.dumps(event),
                MessageAttributes={
                    "event_type": {"DataType": "String", "StringValue": event_type}
                },
            )
            return
        except (ClientError, Exception) as exc:
            logger.warning(
                "SNS attempt %d/%d failed — event_type=%s: %s",
                attempt + 1,
                worker_settings.MAX_SNS_ATTEMPTS,
                event_type,
                exc,
            )
            if attempt < worker_settings.MAX_SNS_ATTEMPTS - 1:
                time.sleep(2**attempt)

    logger.error(
        "SNS gave up after %d attempts — event_type=%s user_id=%s",
        worker_settings.MAX_SNS_ATTEMPTS,
        event_type,
        user_id,
    )
