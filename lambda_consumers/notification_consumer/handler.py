import asyncio
import json
import logging
import os
from decimal import Decimal

import aioboto3
from pydantic import BaseModel

logger = logging.getLogger()
logger.setLevel(logging.INFO)

NOTIFICATION_TOPIC_ARN = os.environ.get("AWS_NOTIFICATION_TOPIC_ARN", "")
AWS_REGION = os.environ.get("AWS_REGION", "eu-west-1")

# Module-level session reused across warm Lambda invocations.
_session = aioboto3.Session()


class _Event(BaseModel):
    event_type: str
    user_id: str
    payload: dict


def lambda_handler(event, context):
    return asyncio.run(_handler(event))


async def _handler(event: dict) -> dict:
    batch_item_failures = []
    for record in event["Records"]:
        try:
            body = json.loads(record["body"])
            raw = json.loads(body["Message"])
            await _process(_Event(**raw))
        except Exception as exc:
            logger.error("Failed %s: %s", record["messageId"], exc, exc_info=True)
            batch_item_failures.append({"itemIdentifier": record["messageId"]})
    return {"batchItemFailures": batch_item_failures}


async def _process(ev: _Event) -> None:
    payload = ev.payload
    goal_name = payload.get("goal_name", "Goal")
    current_amount = Decimal(str(payload.get("current_amount", 0)))
    target_amount = Decimal(str(payload.get("target_amount", 0)))
    progress_pct = float(payload.get("progress_pct", 0))
    days_remaining = int(payload.get("days_remaining", 0))

    # The goal_checker Celery task (Phase 3) already verifies the -20% threshold
    # before emitting goal.progress. This consumer just formats and delivers.
    message = (
        f"FinFlow alert: your goal '{goal_name}' needs attention.\n"
        f"Progress: {progress_pct:.1f}% "
        f"(€{current_amount:.2f} of €{target_amount:.2f})\n"
        f"Days remaining: {days_remaining}"
    )

    if not NOTIFICATION_TOPIC_ARN:
        logger.info(
            "NOTIFICATION_LOCAL user=%s goal=%s progress=%.1f%%",
            ev.user_id,
            goal_name,
            progress_pct,
        )
        return

    await _send_sns(ev.user_id, goal_name, message)


async def _send_sns(user_id: str, goal_name: str, message: str) -> None:
    async with _session.client("sns", region_name=AWS_REGION) as client:
        await client.publish(
            TopicArn=NOTIFICATION_TOPIC_ARN,
            Subject=f"FinFlow: goal alert — {goal_name}",
            Message=message,
            MessageAttributes={
                "user_id": {"DataType": "String", "StringValue": user_id},
            },
        )
    logger.info("Notification sent — user=%s goal=%s", user_id, goal_name)
