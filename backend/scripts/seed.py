#!/usr/bin/env python3
"""Populate the database with realistic demo data.

Run inside the backend container:
    docker compose exec backend python scripts/seed.py
"""
import asyncio
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

DEMO_EMAIL = "demo@finflow.app"
DEMO_PASSWORD = "demo1234"

# Starting balance and date — the user's financial baseline.
INITIAL_BALANCE = Decimal("3500.00")
INITIAL_DATE = date.today() - timedelta(weeks=10)


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


# ---------------------------------------------------------------------------
# Week definitions: weeks_back=0 → current week, 1 → last week, etc.
# Transactions: (name, amount, type, category, is_recurring, recurrence_rule)
# ---------------------------------------------------------------------------
_WEEKS: list[dict] = [
    {
        "weeks_back": 9,
        "transactions": [
            ("Stipendio mensile",    Decimal("2200.00"), "income",  "salary",        True,  "monthly"),
            ("Affitto",              Decimal("800.00"),  "expense", "housing",       True,  "monthly"),
            ("Spesa supermercato",   Decimal("148.50"),  "expense", "food",          True,  "weekly"),
            ("Bolletta elettricità", Decimal("92.40"),   "expense", "utilities",     False, None),
            ("Internet fibra",       Decimal("30.00"),   "expense", "utilities",     True,  "monthly"),
            ("Telefono mobile",      Decimal("14.99"),   "expense", "utilities",     True,  "monthly"),
        ],
    },
    {
        "weeks_back": 8,
        "transactions": [
            ("Rimborso spese aziendali", Decimal("150.00"), "income",  "work",          False, None),
            ("Spesa supermercato",       Decimal("142.80"), "expense", "food",          True,  "weekly"),
            ("Ristorante",               Decimal("67.50"),  "expense", "dining",        False, None),
            ("Benzina",                  Decimal("52.00"),  "expense", "transport",     False, None),
            ("Netflix",                  Decimal("17.99"),  "expense", "entertainment", True,  "monthly"),
            ("Spotify",                  Decimal("10.99"),  "expense", "entertainment", True,  "monthly"),
        ],
    },
    {
        "weeks_back": 7,
        "transactions": [
            ("Spesa supermercato",    Decimal("156.20"), "expense", "food",      True,  "weekly"),
            ("Abbonamento palestra",  Decimal("40.00"),  "expense", "health",    True,  "monthly"),
            ("Abbonamento trasporti", Decimal("60.00"),  "expense", "transport", True,  "monthly"),
            ("Farmacia",              Decimal("34.80"),  "expense", "health",    False, None),
        ],
    },
    {
        "weeks_back": 6,
        "transactions": [
            ("Stipendio mensile",  Decimal("2200.00"), "income",  "salary",     True,  "monthly"),
            ("Dividendi ETF",      Decimal("80.00"),   "income",  "investment", False, None),
            ("Affitto",            Decimal("800.00"),  "expense", "housing",    True,  "monthly"),
            ("Spesa supermercato", Decimal("161.30"),  "expense", "food",       True,  "weekly"),
            ("Bolletta gas",       Decimal("74.60"),   "expense", "utilities",  False, None),
            ("Internet fibra",     Decimal("30.00"),   "expense", "utilities",  True,  "monthly"),
            ("Telefono mobile",    Decimal("14.99"),   "expense", "utilities",  True,  "monthly"),
        ],
    },
    {
        "weeks_back": 5,
        "transactions": [
            ("Rimborso spese aziendali", Decimal("150.00"), "income",  "work",          False, None),
            ("Spesa supermercato",       Decimal("148.90"), "expense", "food",          True,  "weekly"),
            ("Ristorante",               Decimal("82.00"),  "expense", "dining",        False, None),
            ("Abbigliamento",            Decimal("124.50"), "expense", "shopping",      False, None),
            ("Netflix",                  Decimal("17.99"),  "expense", "entertainment", True,  "monthly"),
            ("Spotify",                  Decimal("10.99"),  "expense", "entertainment", True,  "monthly"),
        ],
    },
    {
        "weeks_back": 4,
        "transactions": [
            ("Spesa supermercato",    Decimal("151.40"), "expense", "food",      True,  "weekly"),
            ("Abbonamento palestra",  Decimal("40.00"),  "expense", "health",    True,  "monthly"),
            ("Benzina",               Decimal("56.80"),  "expense", "transport", False, None),
            ("Abbonamento trasporti", Decimal("60.00"),  "expense", "transport", True,  "monthly"),
            ("Farmacia",              Decimal("22.50"),  "expense", "health",    False, None),
        ],
    },
    {
        "weeks_back": 3,
        "transactions": [
            ("Stipendio mensile",        Decimal("2200.00"), "income",  "salary",        True,  "monthly"),
            ("Rimborso spese aziendali", Decimal("150.00"),  "income",  "work",          False, None),
            ("Affitto",                  Decimal("800.00"),  "expense", "housing",       True,  "monthly"),
            ("Spesa supermercato",       Decimal("162.70"),  "expense", "food",          True,  "weekly"),
            ("Bolletta elettricità",     Decimal("87.20"),   "expense", "utilities",     False, None),
            ("Internet fibra",           Decimal("30.00"),   "expense", "utilities",     True,  "monthly"),
            ("Telefono mobile",          Decimal("14.99"),   "expense", "utilities",     True,  "monthly"),
            ("Netflix",                  Decimal("17.99"),   "expense", "entertainment", True,  "monthly"),
            ("Spotify",                  Decimal("10.99"),   "expense", "entertainment", True,  "monthly"),
        ],
    },
    {
        "weeks_back": 2,
        "transactions": [
            ("Dividendi ETF",        Decimal("80.00"),  "income",  "investment",    False, None),
            ("Spesa supermercato",   Decimal("149.80"), "expense", "food",          True,  "weekly"),
            ("Ristorante",           Decimal("58.50"),  "expense", "dining",        False, None),
            ("Abbonamento palestra", Decimal("40.00"),  "expense", "health",        True,  "monthly"),
            ("Benzina",              Decimal("47.60"),  "expense", "transport",     False, None),
            ("Farmacia",             Decimal("16.80"),  "expense", "health",        False, None),
        ],
    },
    {
        "weeks_back": 1,
        "transactions": [
            ("Rimborso spese aziendali", Decimal("150.00"), "income",  "work",          False, None),
            ("Spesa supermercato",       Decimal("157.40"), "expense", "food",          True,  "weekly"),
            ("Abbonamento trasporti",    Decimal("60.00"),  "expense", "transport",     True,  "monthly"),
            ("Abbigliamento",            Decimal("89.00"),  "expense", "shopping",      False, None),
            ("Netflix",                  Decimal("17.99"),  "expense", "entertainment", True,  "monthly"),
            ("Spotify",                  Decimal("10.99"),  "expense", "entertainment", True,  "monthly"),
        ],
    },
    # Current week — still open, partial transactions.
    {
        "weeks_back": 0,
        "transactions": [
            ("Stipendio mensile",  Decimal("2200.00"), "income",  "salary",  True,  "monthly"),
            ("Affitto",            Decimal("800.00"),  "expense", "housing", True,  "monthly"),
            ("Spesa supermercato", Decimal("118.60"),  "expense", "food",    True,  "weekly"),
        ],
    },
]

# Goals use real semantics:
#   liquidity → target is a minimum balance to reach by the date
#   savings   → target is an amount to accumulate from baseline
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

            for name, amount, tx_type, category, is_recurring, recurrence_rule in week_def["transactions"]:
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
                    transaction_date=week_start + timedelta(days=1),
                ))

            if not is_current:
                running_balance = running_balance + net

        # current_balance is the opening of the current week
        # (closing not yet set since the week is still open)
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
    print("Seed complete.")
    print(f"  User:            {DEMO_EMAIL} / {DEMO_PASSWORD}")
    print(f"  Weeks:           {len(_WEEKS)} ({len(_WEEKS) - 1} past + 1 current)")
    print(f"  Transactions:    {total_txs}")
    print(f"  Goals:           {len(_GOALS)}")
    print(f"  Initial balance: €{INITIAL_BALANCE}")
    print(f"  Current opening: €{current_balance}")


if __name__ == "__main__":
    asyncio.run(seed_database())
