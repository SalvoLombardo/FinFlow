from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.goal import Goal, GoalStatus
from app.models.user import User
from app.schemas.dashboard import DashboardSummary, GoalDelta
from app.services.projection import calculate_projection

router = APIRouter()


@router.get("/summary", response_model=DashboardSummary)
async def summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    today = date.today()
    week_monday = today - timedelta(days=today.weekday())
    week_end = week_monday + timedelta(weeks=7)

    projection = await calculate_projection(
        user_id=current_user.id,
        from_week=week_monday,
        to_week=week_end,
        db=db,
    )
    current_balance = projection[0].projected_balance if projection else Decimal("0")

    goals_result = await db.execute(
        select(Goal).where(
            Goal.user_id == current_user.id,
            Goal.status == GoalStatus.active,
        )
    )
    goal_deltas = [
        GoalDelta(
            id=g.id,
            name=g.name,
            target_amount=g.target_amount,
            current_amount=g.current_amount,
            remaining=g.target_amount - g.current_amount,
            target_date=g.target_date,
            status=g.status.value,
        )
        for g in goals_result.scalars().all()
    ]

    return DashboardSummary(
        current_balance=current_balance,
        projection=projection,
        goals=goal_deltas,
    )
