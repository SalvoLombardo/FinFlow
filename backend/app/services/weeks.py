import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import Transaction, TransactionType
from app.models.user_financial_settings import UserFinancialSettings
from app.models.week import FinancialWeek


def week_monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


async def compute_closing(week: FinancialWeek, db: AsyncSession) -> Decimal:
    """Return closing balance for a week: stored value if available, otherwise computed from transactions."""
    if week.closing_balance is not None:
        return week.closing_balance
    txs_result = await db.execute(select(Transaction).where(Transaction.week_id == week.id))
    net = sum(
        (t.amount if t.type == TransactionType.income else -t.amount for t in txs_result.scalars().all()),
        Decimal("0"),
    )
    return week.opening_balance + net


async def get_initial_balance(user_id: uuid.UUID, db: AsyncSession) -> Decimal:
    result = await db.execute(
        select(UserFinancialSettings).where(UserFinancialSettings.user_id == user_id)
    )
    ufs = result.scalar_one_or_none()
    return ufs.initial_balance if ufs else Decimal("0")


async def get_or_create_week(user_id: uuid.UUID, target_date: date, db: AsyncSession) -> FinancialWeek:
    """
    Return the FinancialWeek that contains target_date for user_id.
    If it doesn't exist, create it with opening_balance derived from the chain:
    the closing balance of the most recent existing week before it, or
    UserFinancialSettings.initial_balance if no prior week exists.
    """
    start = week_monday(target_date)
    end = start + timedelta(days=6)

    existing = await db.execute(
        select(FinancialWeek).where(
            FinancialWeek.user_id == user_id,
            FinancialWeek.week_start == start,
        )
    )
    week = existing.scalar_one_or_none()
    if week:
        return week

    prev_result = await db.execute(
        select(FinancialWeek)
        .where(
            FinancialWeek.user_id == user_id,
            FinancialWeek.week_start < start,
        )
        .order_by(FinancialWeek.week_start.desc())
        .limit(1)
    )
    prev = prev_result.scalar_one_or_none()

    if prev is not None:
        opening = await compute_closing(prev, db)
    else:
        opening = await get_initial_balance(user_id, db)

    week = FinancialWeek(
        user_id=user_id,
        week_start=start,
        week_end=end,
        opening_balance=opening,
    )
    db.add(week)
    await db.flush()
    return week
