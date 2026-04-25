import asyncio
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.audit.kafka_producer import AuditEvent, audit_producer
from app.core.database import get_db
from app.events.schemas import EventType, FinFlowEvent
from app.messaging.sns_publisher import sns_publisher
from app.models.user import User
from app.models.week import FinancialWeek
from app.schemas.week import WeekCreate, WeekRead, WeekUpdate

router = APIRouter()


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("/", response_model=list[WeekRead])
async def list_weeks(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(FinancialWeek)
        .where(FinancialWeek.user_id == current_user.id)
        .order_by(FinancialWeek.week_start)
    )
    return result.scalars().all()


@router.post("/", response_model=WeekRead, status_code=status.HTTP_201_CREATED)
async def create_week(
    body: WeekCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    week = FinancialWeek(**body.model_dump(), user_id=current_user.id)
    db.add(week)
    await db.flush()
    return week


@router.get("/{week_id}", response_model=WeekRead)
async def get_week(
    week_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(FinancialWeek).where(
            FinancialWeek.id == week_id,
            FinancialWeek.user_id == current_user.id,
        )
    )
    week = result.scalar_one_or_none()
    if not week:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Week not found")
    return week


@router.put("/{week_id}", response_model=WeekRead)
async def update_week(
    week_id: uuid.UUID,
    request: Request,
    body: WeekUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(FinancialWeek).where(
            FinancialWeek.id == week_id,
            FinancialWeek.user_id == current_user.id,
        )
    )
    week = result.scalar_one_or_none()
    if not week:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Week not found")
    before = WeekRead.model_validate(week).model_dump(mode="json")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(week, field, value)
    if body.closing_balance is not None:
        await sns_publisher.publish(
            FinFlowEvent(
                event_type=EventType.WEEK_CLOSED,
                user_id=str(current_user.id),
                payload={
                    "week_id": str(week.id),
                    "closing_balance": str(week.closing_balance),
                },
            )
        )
    asyncio.create_task(
        audit_producer.send(
            AuditEvent(
                user_id=str(current_user.id),
                action="week.closed" if body.closing_balance is not None else "week.updated",
                entity_type="week",
                entity_id=str(week.id),
                before_state=before,
                after_state=WeekRead.model_validate(week).model_dump(mode="json"),
                ip_address=_client_ip(request),
            )
        )
    )
    return week
