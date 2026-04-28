import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import Transaction, TransactionType
from app.models.week import FinancialWeek
from app.services.weeks import compute_closing, get_initial_balance, week_monday


@dataclass
class WeekSummaryData:
    week_id: uuid.UUID | None
    week_start: date
    week_end: date
    opening_balance: Decimal
    closing_balance: Decimal
    total_income: Decimal
    total_expense: Decimal
    is_projected: bool
    notes: str | None = None


async def _fetch_transactions(week_id: uuid.UUID, db: AsyncSession) -> list[Transaction]:
    result = await db.execute(select(Transaction).where(Transaction.week_id == week_id))
    return result.scalars().all()


def _net(txs: list[Transaction]) -> tuple[Decimal, Decimal, Decimal]:
    """Return (total_income, total_expense, net) for a list of transactions."""
    income = sum((t.amount for t in txs if t.type == TransactionType.income), Decimal("0"))
    expense = sum((t.amount for t in txs if t.type == TransactionType.expense), Decimal("0"))
    return income, expense, income - expense


async def calculate_projection(
    user_id: uuid.UUID,
    n_weeks_back: int,
    n_weeks_forward: int,
    db: AsyncSession,
) -> list[WeekSummaryData]:
    """
    Return week-by-week projection centred on the current week.

    Past/current weeks use real transactions from the DB.
    Future weeks project recurring transactions from the most recent real week.
    Distribution: past = floor((total-1)/2), future = ceil((total-1)/2).
    """
    today = date.today()
    current_monday = week_monday(today)
    from_monday = current_monday - timedelta(weeks=n_weeks_back)
    to_monday = current_monday + timedelta(weeks=n_weeks_forward)

    # Load all DB weeks in range (plus one before for opening balance chain).
    weeks_result = await db.execute(
        select(FinancialWeek)
        .where(
            FinancialWeek.user_id == user_id,
            FinancialWeek.week_start >= from_monday - timedelta(weeks=1),
            FinancialWeek.week_start <= to_monday,
        )
        .order_by(FinancialWeek.week_start)
    )
    all_weeks = weeks_result.scalars().all()
    week_map: dict[date, FinancialWeek] = {w.week_start: w for w in all_weeks}

    # Opening balance: closing of the week just before from_monday (if exists), else initial_balance.
    anchor_week = week_map.get(from_monday - timedelta(weeks=1))
    if anchor_week:
        running = await compute_closing(anchor_week, db)
    else:
        # Look for the most recent week before from_monday not already in week_map.
        last_result = await db.execute(
            select(FinancialWeek)
            .where(
                FinancialWeek.user_id == user_id,
                FinancialWeek.week_start < from_monday,
            )
            .order_by(FinancialWeek.week_start.desc())
            .limit(1)
        )
        last = last_result.scalar_one_or_none()
        running = await compute_closing(last, db) if last else await get_initial_balance(user_id, db)

    # Collect recurring transactions from the most recent real week (for future projection).
    recurring_txs: list[Transaction] = []
    for w in reversed(all_weeks):
        if w.week_start <= current_monday:
            txs = await _fetch_transactions(w.id, db)
            recurring_txs = [t for t in txs if t.is_recurring]
            if recurring_txs:
                break

    result: list[WeekSummaryData] = []
    current = from_monday

    while current <= to_monday:
        week = week_map.get(current)
        is_future = current > current_monday

        if week:
            txs = await _fetch_transactions(week.id, db)
            income, expense, net = _net(txs)
            opening = week.opening_balance
            closing = opening + net
            # Keep running balance in sync with stored opening (handles manual adjustments).
            running = closing
            result.append(WeekSummaryData(
                week_id=week.id,
                week_start=current,
                week_end=current + timedelta(days=6),
                opening_balance=opening,
                closing_balance=closing,
                total_income=income,
                total_expense=expense,
                is_projected=False,
                notes=week.notes,
            ))
        else:
            opening = running
            if is_future:
                income, expense, net = _net(recurring_txs)
            else:
                income, expense, net = Decimal("0"), Decimal("0"), Decimal("0")
            closing = opening + net
            running = closing
            result.append(WeekSummaryData(
                week_id=None,
                week_start=current,
                week_end=current + timedelta(days=6),
                opening_balance=opening,
                closing_balance=closing,
                total_income=income,
                total_expense=expense,
                is_projected=is_future,
            ))

        current += timedelta(weeks=1)

    return result
