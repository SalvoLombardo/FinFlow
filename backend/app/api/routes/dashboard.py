from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.goal import Goal, GoalStatus
from app.models.transaction import Transaction, TransactionType
from app.models.user import User
from app.models.week import FinancialWeek
from app.schemas.dashboard import DashboardSummary, GoalDelta, WeekProjection

router = APIRouter()


@router.get("/summary", response_model=DashboardSummary)
async def summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Current balance: latest week closing_balance or opening_balance
    latest_result = await db.execute(
        select(FinancialWeek)
        .where(FinancialWeek.user_id == current_user.id)
        .order_by(FinancialWeek.week_start.desc())
        .limit(1)
    )
    latest_week = latest_result.scalar_one_or_none()
    if latest_week and latest_week.closing_balance is not None:
        current_balance = latest_week.closing_balance
    elif latest_week:
        current_balance = latest_week.opening_balance
    else:
        current_balance = Decimal("0")

    # 8-week projection starting from current Monday
    today = date.today()
    week_monday = today - timedelta(days=today.weekday())

    future_weeks_result = await db.execute(
        select(FinancialWeek)
        .where(
            FinancialWeek.user_id == current_user.id,
            FinancialWeek.week_start >= week_monday,
        )
        .order_by(FinancialWeek.week_start)
        .limit(8)
    )
    future_weeks = {w.week_start: w for w in future_weeks_result.scalars().all()}

    projection: list[WeekProjection] = []
    running_balance = current_balance
    for i in range(8):
        ws = week_monday + timedelta(weeks=i)
        week = future_weeks.get(ws)
        if week:
            txs_result = await db.execute(
                select(Transaction).where(Transaction.week_id == week.id)
            )
            net = sum(
                (t.amount if t.type == TransactionType.income else -t.amount)
                for t in txs_result.scalars().all()
            )
            running_balance = week.opening_balance + Decimal(str(net))
            projection.append(WeekProjection(week_id=week.id, week_start=ws, projected_balance=running_balance))
        else:
            projection.append(WeekProjection(week_id=None, week_start=ws, projected_balance=running_balance))

    # Active goals with remaining delta
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
