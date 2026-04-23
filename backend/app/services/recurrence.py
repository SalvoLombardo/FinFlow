import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import Transaction
from app.models.week import FinancialWeek


async def apply_recurrences(week_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession) -> None:
    """Copy recurring transactions from the previous week if not already present in week_id."""
    week_result = await db.execute(
        select(FinancialWeek).where(FinancialWeek.id == week_id)
    )
    week = week_result.scalar_one_or_none()
    if not week:
        return

    prev_week_start = week.week_start - timedelta(weeks=1)
    prev_result = await db.execute(
        select(FinancialWeek).where(
            FinancialWeek.user_id == user_id,
            FinancialWeek.week_start == prev_week_start,
        )
    )
    prev_week = prev_result.scalar_one_or_none()
    if not prev_week:
        return

    recurring_result = await db.execute(
        select(Transaction).where(
            Transaction.week_id == prev_week.id,
            Transaction.is_recurring == True,  # noqa: E712
        )
    )
    recurring_txs = recurring_result.scalars().all()
    if not recurring_txs:
        return

    existing_result = await db.execute(
        select(Transaction.name).where(Transaction.week_id == week_id)
    )
    existing_names = {row[0] for row in existing_result.all()}

    for tx in recurring_txs:
        if tx.name not in existing_names:
            db.add(
                Transaction(
                    user_id=user_id,
                    week_id=week_id,
                    name=tx.name,
                    amount=tx.amount,
                    type=tx.type,
                    category=tx.category,
                    is_recurring=True,
                    recurrence_rule=tx.recurrence_rule,
                    notes=tx.notes,
                )
            )
