import asyncio
import json
import logging
import os
import uuid

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_engine = create_async_engine(os.environ["DATABASE_URL"], poolclass=NullPool)
_Session = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


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
    user_uuid = uuid.UUID(ev.user_id)

    async with _Session() as session:
        row = await session.execute(
            text(
                "SELECT ai_enabled, ai_mode, ai_provider, ai_model "
                "FROM user_ai_settings "
                "WHERE user_id = :uid"
            ),
            {"uid": user_uuid},
        )
        ai_settings = row.mappings().one_or_none()

        if not ai_settings or not ai_settings["ai_enabled"]:
            logger.info("AI not enabled for user %s — skipping", ev.user_id)
            return

        provider = ai_settings["ai_provider"] or "unknown"
        model = ai_settings["ai_model"] or "unknown"

        # Phase 5 will replace this stub with real provider calls.
        # The consumer skeleton is intentionally complete so Phase 5 only
        # needs to swap in the actual AI call inside this block.
        content = (
            f"[Phase-5 stub] Analysis triggered by {ev.event_type}. "
            "Configure your AI provider in Settings to receive personalised insights."
        )

        await session.execute(
            text(
                "INSERT INTO ai_insights "
                "  (id, user_id, insight_type, content, model_used, is_read) "
                "VALUES (:id, :uid, :itype, :content, :model, false)"
            ),
            {
                "id": str(uuid.uuid4()),
                "uid": str(user_uuid),
                "itype": ev.event_type,
                "content": content,
                "model": model,
            },
        )
        await session.commit()

    logger.info(
        "Insight saved — event_type=%s user=%s provider=%s model=%s",
        ev.event_type,
        ev.user_id,
        provider,
        model,
    )
