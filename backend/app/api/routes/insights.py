import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.redis_client import check_ai_rate_limit
from app.events.schemas import EventType, FinFlowEvent
from app.messaging.sns_publisher import sns_publisher
from app.models.ai_insight import AIInsight
from app.models.user import User
from app.schemas.insight import AIInsightRead

router = APIRouter()


@router.get("/", response_model=list[AIInsightRead])
async def list_insights(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    offset = (page - 1) * page_size
    result = await db.execute(
        select(AIInsight)
        .where(AIInsight.user_id == current_user.id)
        .order_by(AIInsight.generated_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    return result.scalars().all()


@router.post("/", response_model=dict, status_code=status.HTTP_202_ACCEPTED)
async def request_insight(
    current_user: User = Depends(get_current_user),
):
    allowed = await check_ai_rate_limit(str(current_user.id))
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Daily AI analysis limit reached (max 10 per day).",
        )

    event = FinFlowEvent(
        event_type=EventType.AI_ANALYSIS_REQUESTED,
        user_id=str(current_user.id),
        payload={"trigger": "manual", "insight_type": "savings_tip"},
    )
    await sns_publisher.publish(event)
    return {"status": "queued"}


@router.put("/{insight_id}/read", response_model=AIInsightRead)
async def mark_insight_read(
    insight_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AIInsight).where(
            AIInsight.id == insight_id,
            AIInsight.user_id == current_user.id,
        )
    )
    insight = result.scalar_one_or_none()
    if insight is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Insight not found.")
    insight.is_read = True
    await db.flush()
    return insight
