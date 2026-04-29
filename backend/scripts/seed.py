#!/usr/bin/env python3
"""Populate the database with realistic demo data.

Run inside the backend container:
    docker compose exec backend python scripts/seed.py
"""
import asyncio
import calendar
import sys
import uuid
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models  # noqa: F401
from app.core.config import settings
from app.models.goal import Goal, GoalStatus, GoalType
from app.models.transaction import Transaction, TransactionType
from app.models.user import User
from app.models.user_financial_settings import UserFinancialSettings
from app.models.week import FinancialWeek
from app.services.auth import hash_password

DEMO_EMAIL = "admin@admin.com"
DEMO_PASSWORD = "Prova1234@"

INITIAL_BALANCE = Decimal("3500.00")
INITIAL_DATE = date.today() - timedelta(weeks=10)


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _add_months(d: date, months: int) -> date:
    """Add `months` months to a date, clamping to the last day of the target month."""
    m = d.month - 1 + months
    y = d.year + m // 12
    m = m % 12 + 1
    last = calendar.monthrange(y, m)[1]
    return d.replace(year=y, month=m, day=min(d.day, last))


# ---------------------------------------------------------------------------
# Pre-compute end dates for demo recurring transactions (all relative to today).
# ---------------------------------------------------------------------------
_TODAY = date.today()
_CURRENT_MONDAY = _monday(_TODAY)

# "Regalo mensile Marco" — started ~1 week ago, stops at end of current year.
_GIFT_END = date(_TODAY.year, 12, 31)

# "Rata finanziamento PC" — started ~2 weeks ago, 12 installments at M:1.
_LOAN_START = _CURRENT_MONDAY - timedelta(weeks=2) + timedelta(days=1)
_LOAN_END = _add_months(_LOAN_START, 11)  # 12th and last installment


# ---------------------------------------------------------------------------
# Week definitions.
# Tuple: (name, amount, type, category, is_recurring, recurrence_rule, recurrence_end_date)
# ---------------------------------------------------------------------------
_WEEKS: list[dict] = [
    {
        "weeks_back": 9,
        "transactions": [
            ("Stipendio mensile",    Decimal("2200.00"), "income",  "salary",        True,  "M:1", None),
            ("Affitto",              Decimal("800.00"),  "expense", "housing",       True,  "M:1", None),
            ("Spesa supermercato",   Decimal("148.50"),  "expense", "food",          True,  "W:1", None),
            ("Bolletta elettricità", Decimal("92.40"),   "expense", "utilities",     False, None,  None),
            ("Internet fibra",       Decimal("30.00"),   "expense", "utilities",     True,  "M:1", None),
            ("Telefono mobile",      Decimal("14.99"),   "expense", "utilities",     True,  "M:1", None),
        ],
    },
    {
        "weeks_back": 8,
        "transactions": [
            ("Rimborso spese aziendali", Decimal("150.00"), "income",  "work",          False, None,  None),
            ("Spesa supermercato",       Decimal("142.80"), "expense", "food",          True,  "W:1", None),
            ("Ristorante",               Decimal("67.50"),  "expense", "dining",        False, None,  None),
            ("Benzina",                  Decimal("52.00"),  "expense", "transport",     False, None,  None),
            ("Netflix",                  Decimal("17.99"),  "expense", "entertainment", True,  "M:1", None),
            ("Spotify",                  Decimal("10.99"),  "expense", "entertainment", True,  "M:1", None),
        ],
    },
    {
        "weeks_back": 7,
        "transactions": [
            ("Spesa supermercato",    Decimal("156.20"), "expense", "food",      True,  "W:1", None),
            ("Abbonamento palestra",  Decimal("40.00"),  "expense", "health",    True,  "M:1", None),
            ("Abbonamento trasporti", Decimal("60.00"),  "expense", "transport", True,  "M:1", None),
            ("Farmacia",              Decimal("34.80"),  "expense", "health",    False, None,  None),
        ],
    },
    {
        "weeks_back": 6,
        "transactions": [
            ("Stipendio mensile",  Decimal("2200.00"), "income",  "salary",     True,  "M:1", None),
            ("Dividendi ETF",      Decimal("80.00"),   "income",  "investment", False, None,  None),
            ("Affitto",            Decimal("800.00"),  "expense", "housing",    True,  "M:1", None),
            ("Spesa supermercato", Decimal("161.30"),  "expense", "food",       True,  "W:1", None),
            ("Bolletta gas",       Decimal("74.60"),   "expense", "utilities",  False, None,  None),
            ("Internet fibra",     Decimal("30.00"),   "expense", "utilities",  True,  "M:1", None),
            ("Telefono mobile",    Decimal("14.99"),   "expense", "utilities",  True,  "M:1", None),
        ],
    },
    {
        "weeks_back": 5,
        "transactions": [
            ("Rimborso spese aziendali", Decimal("150.00"), "income",  "work",          False, None,  None),
            ("Spesa supermercato",       Decimal("148.90"), "expense", "food",          True,  "W:1", None),
            ("Ristorante",               Decimal("82.00"),  "expense", "dining",        False, None,  None),
            ("Abbigliamento",            Decimal("124.50"), "expense", "shopping",      False, None,  None),
            ("Netflix",                  Decimal("17.99"),  "expense", "entertainment", True,  "M:1", None),
            ("Spotify",                  Decimal("10.99"),  "expense", "entertainment", True,  "M:1", None),
        ],
    },
    {
        "weeks_back": 4,
        "transactions": [
            ("Spesa supermercato",    Decimal("151.40"), "expense", "food",      True,  "W:1", None),
            ("Abbonamento palestra",  Decimal("40.00"),  "expense", "health",    True,  "M:1", None),
            ("Benzina",               Decimal("56.80"),  "expense", "transport", False, None,  None),
            ("Abbonamento trasporti", Decimal("60.00"),  "expense", "transport", True,  "M:1", None),
            ("Farmacia",              Decimal("22.50"),  "expense", "health",    False, None,  None),
        ],
    },
    {
        "weeks_back": 3,
        "transactions": [
            ("Stipendio mensile",        Decimal("2200.00"), "income",  "salary",        True,  "M:1", None),
            ("Rimborso spese aziendali", Decimal("150.00"),  "income",  "work",          False, None,  None),
            ("Affitto",                  Decimal("800.00"),  "expense", "housing",       True,  "M:1", None),
            ("Spesa supermercato",       Decimal("162.70"),  "expense", "food",          True,  "W:1", None),
            ("Bolletta elettricità",     Decimal("87.20"),   "expense", "utilities",     False, None,  None),
            ("Internet fibra",           Decimal("30.00"),   "expense", "utilities",     True,  "M:1", None),
            ("Telefono mobile",          Decimal("14.99"),   "expense", "utilities",     True,  "M:1", None),
            ("Netflix",                  Decimal("17.99"),   "expense", "entertainment", True,  "M:1", None),
            ("Spotify",                  Decimal("10.99"),   "expense", "entertainment", True,  "M:1", None),
        ],
    },
    {
        "weeks_back": 2,
        # Demo: "Rata finanziamento PC" — 12 rate M:1, finisce in ~10 mesi.
        "transactions": [
            ("Dividendi ETF",        Decimal("80.00"),  "income",  "investment",    False, None,  None),
            ("Spesa supermercato",   Decimal("149.80"), "expense", "food",          True,  "W:1", None),
            ("Ristorante",           Decimal("58.50"),  "expense", "dining",        False, None,  None),
            ("Abbonamento palestra", Decimal("40.00"),  "expense", "health",        True,  "M:1", None),
            ("Benzina",              Decimal("47.60"),  "expense", "transport",     False, None,  None),
            ("Farmacia",             Decimal("16.80"),  "expense", "health",        False, None,  None),
            ("Rata finanziamento PC",Decimal("85.00"),  "expense", "loan",          True,  "M:1", _LOAN_END),
        ],
    },
    {
        "weeks_back": 1,
        # Demo: "Regalo mensile Marco" — M:1, finisce il 31/12 dell'anno in corso.
        "transactions": [
            ("Rimborso spese aziendali", Decimal("150.00"), "income",  "work",          False, None,       None),
            ("Spesa supermercato",       Decimal("157.40"), "expense", "food",          True,  "W:1",      None),
            ("Abbonamento trasporti",    Decimal("60.00"),  "expense", "transport",     True,  "M:1",      None),
            ("Abbigliamento",            Decimal("89.00"),  "expense", "shopping",      False, None,       None),
            ("Netflix",                  Decimal("17.99"),  "expense", "entertainment", True,  "M:1",      None),
            ("Spotify",                  Decimal("10.99"),  "expense", "entertainment", True,  "M:1",      None),
            ("Regalo mensile Marco",     Decimal("50.00"),  "expense", "gifts",         True,  "M:1",      _GIFT_END),
        ],
    },
    # Current week — still open, partial transactions.
    {
        "weeks_back": 0,
        "transactions": [
            ("Stipendio mensile",  Decimal("2200.00"), "income",  "salary",  True,  "M:1", None),
            ("Affitto",            Decimal("800.00"),  "expense", "housing", True,  "M:1", None),
            ("Spesa supermercato", Decimal("118.60"),  "expense", "food",    True,  "W:1", None),
        ],
    },
]

_GOALS = [
    {
        "name": "Fondo d'emergenza",
        "goal_type": GoalType.liquidity,
        "target_amount": Decimal("6000.00"),
        "target_date": date(2026, 12, 31),
    },
    {
        "name": "Vacanza in Grecia",
        "goal_type": GoalType.savings,
        "target_amount": Decimal("1500.00"),
        "target_date": date(2026, 7, 15),
    },
    {
        "name": "Nuovo MacBook Pro",
        "goal_type": GoalType.savings,
        "target_amount": Decimal("2000.00"),
        "target_date": date(2026, 10, 31),
    },
]


async def seed_database() -> None:
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as session:
        existing = await session.execute(select(User).where(User.email == DEMO_EMAIL))
        if existing.scalar_one_or_none() is not None:
            print("Seed data already present — nothing to do.")
            await engine.dispose()
            return

        # --- User ---
        user = User(
            id=uuid.uuid4(),
            email=DEMO_EMAIL,
            hashed_password=hash_password(DEMO_PASSWORD),
        )
        session.add(user)
        await session.flush()

        # --- UserFinancialSettings ---
        session.add(UserFinancialSettings(
            id=uuid.uuid4(),
            user_id=user.id,
            initial_balance=INITIAL_BALANCE,
            initial_balance_date=INITIAL_DATE,
        ))
        await session.flush()

        # --- Weeks + Transactions ---
        current_monday = _monday(date.today())
        running_balance = INITIAL_BALANCE

        for week_def in _WEEKS:
            weeks_back: int = week_def["weeks_back"]
            week_start = current_monday - timedelta(weeks=weeks_back)
            week_end = week_start + timedelta(days=6)
            is_current = weeks_back == 0

            net = Decimal("0")
            for tx in week_def["transactions"]:
                _, amount, tx_type, *_ = tx
                net += amount if tx_type == "income" else -amount

            closing = None if is_current else running_balance + net

            week = FinancialWeek(
                id=uuid.uuid4(),
                user_id=user.id,
                week_start=week_start,
                week_end=week_end,
                opening_balance=running_balance,
                closing_balance=closing,
            )
            session.add(week)
            await session.flush()

            for name, amount, tx_type, category, is_recurring, recurrence_rule, recurrence_end_date in week_def["transactions"]:
                session.add(Transaction(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    week_id=week.id,
                    name=name,
                    amount=amount,
                    type=TransactionType(tx_type),
                    category=category,
                    is_recurring=is_recurring,
                    recurrence_rule=recurrence_rule,
                    recurrence_end_date=recurrence_end_date,
                    transaction_date=week_start + timedelta(days=1),
                ))

            if not is_current:
                running_balance = running_balance + net

        current_balance = running_balance

        # --- Goals ---
        for goal_def in _GOALS:
            goal_type = goal_def["goal_type"]
            baseline = current_balance if goal_type == GoalType.savings else None
            current_amount = current_balance if goal_type == GoalType.liquidity else Decimal("0")

            session.add(Goal(
                id=uuid.uuid4(),
                user_id=user.id,
                name=goal_def["name"],
                goal_type=goal_type,
                target_amount=goal_def["target_amount"],
                target_date=goal_def["target_date"],
                baseline_balance=baseline,
                current_amount=current_amount,
                status=GoalStatus.active,
            ))

        await session.commit()

    await engine.dispose()

    total_txs = sum(len(w["transactions"]) for w in _WEEKS)
    with_end_date = sum(
        1 for w in _WEEKS for tx in w["transactions"] if tx[6] is not None
    )
    print("Seed complete.")
    print(f"  User:             {DEMO_EMAIL} / {DEMO_PASSWORD}")
    print(f"  Weeks:            {len(_WEEKS)} ({len(_WEEKS) - 1} past + 1 current)")
    print(f"  Transactions:     {total_txs} ({with_end_date} with recurrence_end_date)")
    print(f"  Goals:            {len(_GOALS)}")
    print(f"  Initial balance:  €{INITIAL_BALANCE}")
    print(f"  Current opening:  €{current_balance}")
    print(f"  Loan end date:    {_LOAN_END}  (Rata finanziamento PC)")
    print(f"  Gift end date:    {_GIFT_END}  (Regalo mensile Marco)")


if __name__ == "__main__":
    asyncio.run(seed_database())
