import asyncio
import json
import logging
import os
import uuid
from datetime import date, timedelta
from decimal import Decimal

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# NullPool: avoids stale connections across Lambda invocations with different event loops.
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
    today = date.today()
    week_start = today - timedelta(days=today.weekday())  # Monday
    week_end = week_start + timedelta(weeks=8)

    async with _Session() as session:
        result = await session.execute(
            text(
                "SELECT id, week_start, opening_balance "
                "FROM financial_weeks "
                "WHERE user_id = :uid "
                "  AND week_start >= :ws "
                "  AND week_start <= :we "
                "ORDER BY week_start"
            ),
            {"uid": user_uuid, "ws": week_start, "we": week_end},
        )
        weeks = result.mappings().all()

        if not weeks:
            logger.info("No weeks found for user %s in range", ev.user_id)
            return

        for week in weeks:
            txs = await session.execute(
                text("SELECT amount, type FROM transactions WHERE week_id = :wid"),
                {"wid": week["id"]},
            )
            net = Decimal("0")
            for tx in txs.mappings().all():
                amount = Decimal(str(tx["amount"]))
                net += amount if tx["type"] == "income" else -amount

            closing = Decimal(str(week["opening_balance"])) + net
            await session.execute(
                text("UPDATE financial_weeks SET closing_balance = :cb WHERE id = :wid"),
                {"cb": closing, "wid": week["id"]},
            )

        # Mark goals as achieved when current_amount reaches target_amount.
        goals = await session.execute(
            text(
                "SELECT id, target_amount, current_amount "
                "FROM goals "
                "WHERE user_id = :uid AND status = 'active'"
            ),
            {"uid": user_uuid},
        )
        for goal in goals.mappings().all():
            if Decimal(str(goal["current_amount"])) >= Decimal(str(goal["target_amount"])):
                await session.execute(
                    text("UPDATE goals SET status = 'achieved' WHERE id = :gid"),
                    {"gid": goal["id"]},
                )
                logger.info("Goal %s marked as achieved for user %s", goal["id"], ev.user_id)

        await session.commit()

    logger.info(
        "Projection updated — event_type=%s user=%s weeks_processed=%d",
        ev.event_type,
        ev.user_id,
        len(weeks),
    )
