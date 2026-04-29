import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.models.week import FinancialWeek
from app.schemas.week import ProjectedTransaction, ProjectedWeekDetail, WeekRead, WeekSummary, WeekUpdate
from app.services.projection import (
    _fetch_canonical_recurring,
    _should_apply_in_week,
    calculate_projection,
)
from app.services.weeks import week_monday

router = APIRouter()


@router.get("", response_model=list[WeekSummary])
async def list_weeks(
    range: int = Query(default=12, ge=4, le=52, description="Total weeks to show (4, 8 or 12)."),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    n_past = (range - 1) // 2
    n_future = (range - 1) - n_past
    summaries = await calculate_projection(
        user_id=current_user.id,
        n_weeks_back=n_past,
        n_weeks_forward=n_future,
        db=db,
    )
    return [
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


@router.get("/projected", response_model=ProjectedWeekDetail)
async def get_projected_week(
    week_start: date = Query(..., description="Monday of the target future week (YYYY-MM-DD)."),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    target_monday = week_monday(week_start)
    today_monday = week_monday(date.today())

    if target_monday <= today_monday:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="week_start must be in the future (strictly after the current week).",
        )

    n_forward = (target_monday - today_monday).days // 7
    summaries = await calculate_projection(
        user_id=current_user.id,
        n_weeks_back=0,
        n_weeks_forward=n_forward,
        db=db,
    )

    target = next((s for s in summaries if s.week_start == target_monday), None)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projected week not found.")

    recurring_txs = await _fetch_canonical_recurring(current_user.id, db)
    applicable = [t for t in recurring_txs if _should_apply_in_week(t, target_monday)]

    return ProjectedWeekDetail(
        week_start=target.week_start,
        week_end=target.week_start + timedelta(days=6),
        opening_balance=float(target.opening_balance),
        closing_balance=float(target.closing_balance),
        total_income=float(target.total_income),
        total_expense=float(target.total_expense),
        transactions=[
            ProjectedTransaction(
                id=t.id,
                name=t.name,
                amount=float(t.amount),
                type=t.type,
                category=t.category,
                recurrence_rule=t.recurrence_rule,
                recurrence_end_date=t.recurrence_end_date,
            )
            for t in applicable
        ],
    )


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
    if body.notes is not None:
        week.notes = body.notes
    return week
