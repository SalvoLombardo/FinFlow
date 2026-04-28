import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.goal import Goal, GoalType
from app.models.user import User
from app.schemas.goal import GoalCreate, GoalRead, GoalUpdate
from app.services.weeks import get_initial_balance, week_monday
from app.services.projection import calculate_projection

router = APIRouter()


async def _current_balance(user_id: uuid.UUID, db: AsyncSession) -> Decimal:
    """Return the current week's closing balance (real transactions, no projection)."""
    summaries = await calculate_projection(user_id=user_id, n_weeks_back=0, n_weeks_forward=0, db=db)
    if summaries:
        return summaries[0].closing_balance
    return await get_initial_balance(user_id, db)


@router.get("", response_model=list[GoalRead])
async def list_goals(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Goal).where(Goal.user_id == current_user.id).order_by(Goal.created_at)
    )
    goals = result.scalars().all()

    balance = await _current_balance(current_user.id, db)

    for goal in goals:
        if goal.goal_type == GoalType.liquidity:
            goal.current_amount = balance
        else:
            baseline = goal.baseline_balance if goal.baseline_balance is not None else Decimal("0")
            goal.current_amount = max(balance - baseline, Decimal("0"))

    return goals


@router.post("", response_model=GoalRead, status_code=status.HTTP_201_CREATED)
async def create_goal(
    body: GoalCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    balance = await _current_balance(current_user.id, db)

    goal = Goal(
        user_id=current_user.id,
        name=body.name,
        target_amount=body.target_amount,
        target_date=body.target_date,
        goal_type=body.goal_type,
        baseline_balance=balance if body.goal_type == GoalType.savings else None,
        current_amount=balance if body.goal_type == GoalType.liquidity else Decimal("0"),
    )
    db.add(goal)
    await db.flush()
    return goal


@router.put("/{goal_id}", response_model=GoalRead)
async def update_goal(
    goal_id: uuid.UUID,
    body: GoalUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Goal).where(Goal.id == goal_id, Goal.user_id == current_user.id)
    )
    goal = result.scalar_one_or_none()
    if not goal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(goal, field, value)

    # Refresh current_amount after any update.
    balance = await _current_balance(current_user.id, db)
    if goal.goal_type == GoalType.liquidity:
        goal.current_amount = balance
    else:
        baseline = goal.baseline_balance if goal.baseline_balance is not None else Decimal("0")
        goal.current_amount = max(balance - baseline, Decimal("0"))

    return goal
