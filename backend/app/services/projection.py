import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import Transaction, TransactionType
from app.models.week import FinancialWeek
from app.schemas.dashboard import WeekProjection
from app.services.recurrence import apply_recurrences


async def calculate_projection(
    user_id: uuid.UUID,
    from_week: date,
    to_week: date,
    db: AsyncSession,
) -> list[WeekProjection]:
    """
    Compute week-by-week balance from from_week to to_week (inclusive, 7-day steps).
    For each existing week: apply recurrences, sum transactions, update running balance.
    For missing weeks: carry forward the last known balance.
    """
    weeks_result = await db.execute(
        select(FinancialWeek)
        .where(
            FinancialWeek.user_id == user_id,
            FinancialWeek.week_start >= from_week,
            FinancialWeek.week_start <= to_week,
        )
        .order_by(FinancialWeek.week_start)
    )
    weeks = weeks_result.scalars().all()
    week_map: dict[date, FinancialWeek] = {w.week_start: w for w in weeks}

    first_week = week_map.get(from_week)
    running_balance: Decimal = first_week.opening_balance if first_week else Decimal("0")

    projections: list[WeekProjection] = []
    current = from_week
    while current <= to_week:
        week = week_map.get(current)
        if week:
            await apply_recurrences(week.id, user_id, db)
            txs_result = await db.execute(
                select(Transaction).where(Transaction.week_id == week.id)
            )
            net = sum(
                (t.amount if t.type == TransactionType.income else -t.amount
                 for t in txs_result.scalars().all()),
                Decimal("0"),
            )
            running_balance = week.opening_balance + net

        projections.append(
            WeekProjection(
                week_id=week.id if week else None,
                week_start=current,
                projected_balance=running_balance,
            )
        )
        current += timedelta(weeks=1)

    return projections
