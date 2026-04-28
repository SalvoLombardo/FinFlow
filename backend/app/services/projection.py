import calendar as _calendar
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


async def _fetch_canonical_recurring(user_id: uuid.UUID, db: AsyncSession) -> list[Transaction]:
    """Return the most recent instance of each unique recurring transaction for the user."""
    result = await db.execute(
        select(Transaction)
        .where(Transaction.user_id == user_id, Transaction.is_recurring == True)  # noqa: E712
        .order_by(Transaction.transaction_date.desc().nullslast())
    )
    all_recurring = result.scalars().all()
    seen: dict[tuple, Transaction] = {}
    for tx in all_recurring:
        key = (tx.name, tx.type, tx.category)
        if key not in seen:
            seen[key] = tx
    return list(seen.values())


def _parse_rule(rule: str | None) -> tuple[str, int]:
    """Parse recurrence_rule into (unit, interval). Defaults to W:1 (weekly)."""
    if not rule:
        return "W", 1
    parts = rule.split(":")
    if len(parts) != 2:
        return "W", 1
    unit = parts[0].upper()
    try:
        interval = max(1, int(parts[1]))
    except ValueError:
        return "W", 1
    if unit not in ("W", "M", "Y"):
        return "W", 1
    return unit, interval


def _should_apply_in_week(tx: Transaction, target_monday: date) -> bool:
    """True if tx should appear in the projected week starting at target_monday."""
    unit, interval = _parse_rule(tx.recurrence_rule)
    origin = tx.transaction_date or tx.created_at.date()
    origin_monday = week_monday(origin)

    if unit == "W":
        weeks_diff = (target_monday - origin_monday).days // 7
        return weeks_diff > 0 and weeks_diff % interval == 0

    if unit == "M":
        origin_day = origin.day
        for offset in range(7):
            d = target_monday + timedelta(days=offset)
            last_day = _calendar.monthrange(d.year, d.month)[1]
            # Clamp day to valid range (e.g. Jan 31 → Feb 28).
            effective_day = min(origin_day, last_day)
            if d.day == effective_day:
                months_diff = (d.year - origin.year) * 12 + (d.month - origin.month)
                return months_diff > 0 and months_diff % interval == 0
        return False

    if unit == "Y":
        for offset in range(7):
            d = target_monday + timedelta(days=offset)
            if d.month == origin.month:
                last_day = _calendar.monthrange(d.year, d.month)[1]
                effective_day = min(origin.day, last_day)
                if d.day == effective_day:
                    years_diff = d.year - origin.year
                    return years_diff > 0 and years_diff % interval == 0
        return False

    return False


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
    Future weeks project recurring transactions filtered by recurrence_rule frequency.
    Distribution: past = n_weeks_back, future = n_weeks_forward.
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

    # Opening balance anchor.
    anchor_week = week_map.get(from_monday - timedelta(weeks=1))
    if anchor_week:
        running = await compute_closing(anchor_week, db)
    else:
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

    # One canonical instance per unique (name, type, category) recurring transaction.
    recurring_txs = await _fetch_canonical_recurring(user_id, db)

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
                applicable = [t for t in recurring_txs if _should_apply_in_week(t, current)]
                income, expense, net = _net(applicable)
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
