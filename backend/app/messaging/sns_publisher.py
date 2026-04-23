import asyncio
import logging

import aioboto3

from app.core.config import settings
from app.events.schemas import FinFlowEvent

logger = logging.getLogger(__name__)

_MAX_ATTEMPTS = 3

# Module-level session: lightweight, safe to share across async calls.
_session = aioboto3.Session()


class SNSPublisher:
    """Publishes FinFlowEvents to SNS.

    When AWS_SNS_TOPIC_ARN is empty (local / CI), logs the event as
    structured JSON instead of calling AWS — no credentials required.
    """

    async def publish(self, event: FinFlowEvent) -> None:
        if not settings.AWS_SNS_TOPIC_ARN:
            logger.info(
                "SNS_LOCAL event_type=%s user_id=%s body=%s",
                event.event_type.value,
                event.user_id,
                event.model_dump_json(),
            )
            return

        for attempt in range(_MAX_ATTEMPTS):
            try:
                await self._send(event)
                return
            except Exception as exc:
                logger.warning(
                    "SNS publish attempt %d/%d failed — event_type=%s: %s",
                    attempt + 1,
                    _MAX_ATTEMPTS,
                    event.event_type.value,
                    exc,
                )
                if attempt < _MAX_ATTEMPTS - 1:
                    await asyncio.sleep(2**attempt)  # 1s, 2s

        logger.error(
            "SNS publish gave up after %d attempts — event_type=%s user_id=%s",
            _MAX_ATTEMPTS,
            event.event_type.value,
            event.user_id,
        )

    async def _send(self, event: FinFlowEvent) -> None:
        async with _session.client("sns", region_name=settings.AWS_REGION) as client:
            await client.publish(
                TopicArn=settings.AWS_SNS_TOPIC_ARN,
                Message=event.model_dump_json(),
                MessageAttributes={
                    "event_type": {
                        "DataType": "String",
                        "StringValue": event.event_type.value,
                    }
                },
            )


# Singleton exported for use in route handlers.
sns_publisher = SNSPublisher()
