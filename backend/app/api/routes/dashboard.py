from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.goal import Goal, GoalStatus, GoalType
from app.models.user import User
from app.schemas.dashboard import DashboardSummary, GoalDelta
from app.schemas.week import WeekSummary
from app.services.projection import calculate_projection
from app.services.weeks import get_initial_balance

router = APIRouter()


@router.get("/summary", response_model=DashboardSummary)
async def summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # 8 weeks total: current + 7 future (standard dashboard horizon).
    summaries = await calculate_projection(
        user_id=current_user.id,
        n_weeks_back=0,
        n_weeks_forward=7,
        db=db,
    )

    week_views = [
        WeekSummary(
            week_id=s.week_id,
            week_start=s.week_start,
            week_end=s.week_end,
            opening_balance=float(s.opening_balance),
            closing_balance=float(s.closing_balance),
            total_income=float(s.total_income),
            total_expense=float(s.total_expense),
            net=float(s.total_income - s.total_expense),
            is_projected=s.is_projected,
            notes=s.notes,
        )
        for s in summaries
    ]

    current_balance: Decimal = summaries[0].closing_balance if summaries else await get_initial_balance(
        current_user.id, db
    )

    goals_result = await db.execute(
        select(Goal).where(
            Goal.user_id == current_user.id,
            Goal.status == GoalStatus.active,
        )
    )
    goal_deltas = []
    for g in goals_result.scalars().all():
        if g.goal_type == GoalType.liquidity:
            current = float(current_balance)
        else:
            baseline = float(g.baseline_balance) if g.baseline_balance is not None else 0.0
            current = max(float(current_balance) - baseline, 0.0)

        target = float(g.target_amount)
        progress_pct = min(round((current / target * 100) if target > 0 else 100.0, 1), 100.0)
        goal_deltas.append(GoalDelta(
            id=g.id,
            name=g.name,
            target_amount=target,
            current_amount=current,
            remaining=max(target - current, 0.0),
            progress_pct=progress_pct,
            target_date=g.target_date,
            goal_type=g.goal_type.value,
            status=g.status.value,
        ))

    return DashboardSummary(
        current_balance=float(current_balance),
        projection=week_views,
        goals=goal_deltas,
    )
