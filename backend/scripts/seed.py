#!/usr/bin/env python3
"""Populate the database with realistic demo data.

Run inside the backend container:
    docker compose exec backend python scripts/seed.py
"""
import asyncio
import sys
import uuid
from datetime import date, timedelta
from pathlib import Path

# Ensure the project root (/app inside Docker, backend/ locally) is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models  # noqa: F401 — registers all models with Base
from app.core.config import settings
from app.models.goal import Goal, GoalStatus
from app.models.transaction import Transaction, TransactionType
from app.models.user import User
from app.models.week import FinancialWeek
from app.services.auth import hash_password

DEMO_EMAIL = "demo@finflow.app"
DEMO_PASSWORD = "demo1234"


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


# ---------------------------------------------------------------------------
# Week definitions: (weeks_back_from_current, list_of_transactions)
# transactions: (name, amount, type, category, is_recurring, recurrence_rule)
# ---------------------------------------------------------------------------

# opening_balance of the very first week
_FIRST_OPENING = Decimal("3500.00")

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
            ("Stipendio mensile",  Decimal("2200.00"), "income",  "salary",    True,  "monthly"),
            ("Dividendi ETF",      Decimal("80.00"),   "income",  "investment", False, None),
            ("Affitto",            Decimal("800.00"),  "expense", "housing",   True,  "monthly"),
            ("Spesa supermercato", Decimal("161.30"),  "expense", "food",      True,  "weekly"),
            ("Bolletta gas",       Decimal("74.60"),   "expense", "utilities", False, None),
            ("Internet fibra",     Decimal("30.00"),   "expense", "utilities", True,  "monthly"),
            ("Telefono mobile",    Decimal("14.99"),   "expense", "utilities", True,  "monthly"),
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
            ("Stipendio mensile",    Decimal("2200.00"), "income",  "salary",        True,  "monthly"),
            ("Rimborso spese aziendali", Decimal("150.00"), "income", "work",        False, None),
            ("Affitto",              Decimal("800.00"),  "expense", "housing",       True,  "monthly"),
            ("Spesa supermercato",   Decimal("162.70"),  "expense", "food",          True,  "weekly"),
            ("Bolletta elettricità", Decimal("87.20"),   "expense", "utilities",     False, None),
            ("Internet fibra",       Decimal("30.00"),   "expense", "utilities",     True,  "monthly"),
            ("Telefono mobile",      Decimal("14.99"),   "expense", "utilities",     True,  "monthly"),
            ("Netflix",              Decimal("17.99"),   "expense", "entertainment", True,  "monthly"),
            ("Spotify",              Decimal("10.99"),   "expense", "entertainment", True,  "monthly"),
        ],
    },
    {
        "weeks_back": 2,
        "transactions": [
            ("Dividendi ETF",         Decimal("80.00"),  "income",  "investment",    False, None),
            ("Spesa supermercato",    Decimal("149.80"), "expense", "food",          True,  "weekly"),
            ("Ristorante",            Decimal("58.50"),  "expense", "dining",        False, None),
            ("Abbonamento palestra",  Decimal("40.00"),  "expense", "health",        True,  "monthly"),
            ("Benzina",               Decimal("47.60"),  "expense", "transport",     False, None),
            ("Farmacia",              Decimal("16.80"),  "expense", "health",        False, None),
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
    # Current week — no closing_balance (still open)
    {
        "weeks_back": 0,
        "transactions": [
            ("Stipendio mensile",  Decimal("2200.00"), "income",  "salary",  True,  "monthly"),
            ("Affitto",            Decimal("800.00"),  "expense", "housing", True,  "monthly"),
            ("Spesa supermercato", Decimal("118.60"),  "expense", "food",    True,  "weekly"),
        ],
    },
]

_GOALS = [
    {
        "name": "Fondo d'emergenza",
        "target_amount": Decimal("5000.00"),
        "current_amount": Decimal("1500.00"),
        "target_date": date(2026, 12, 31),
        "status": GoalStatus.active,
    },
    {
        "name": "Vacanza in Grecia",
        "target_amount": Decimal("2500.00"),
        "current_amount": Decimal("850.00"),
        "target_date": date(2026, 7, 15),
        "status": GoalStatus.active,
    },
    {
        "name": "Nuovo MacBook Pro",
        "target_amount": Decimal("2000.00"),
        "current_amount": Decimal("350.00"),
        "target_date": date(2026, 10, 31),
        "status": GoalStatus.active,
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

        # --- Weeks + transactions ---
        current_monday = _monday(date.today())
        running_balance = _FIRST_OPENING
        current_week_opening = _FIRST_OPENING

        for week_def in _WEEKS:
            weeks_back: int = week_def["weeks_back"]
            week_start = current_monday - timedelta(weeks=weeks_back)
            week_end = week_start + timedelta(days=6)
            is_current = weeks_back == 0

            # Calculate net for this week to derive closing balance
            net = Decimal("0")
            for tx in week_def["transactions"]:
                _, amount, tx_type, *_ = tx
                if tx_type == "income":
                    net += amount
                else:
                    net -= amount

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
                tx_date = week_start + timedelta(days=1)  # default: Tuesday of the week
                session.add(
                    Transaction(
                        id=uuid.uuid4(),
                        user_id=user.id,
                        week_id=week.id,
                        name=name,
                        amount=amount,
                        type=TransactionType(tx_type),
                        category=category,
                        is_recurring=is_recurring,
                        recurrence_rule=recurrence_rule,
                        transaction_date=tx_date,
                    )
                )

            if is_current:
                current_week_opening = running_balance
            else:
                running_balance = running_balance + net

        # --- Goals ---
        for goal_def in _GOALS:
            session.add(
                Goal(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    name=goal_def["name"],
                    target_amount=goal_def["target_amount"],
                    current_amount=goal_def["current_amount"],
                    target_date=goal_def["target_date"],
                    status=goal_def["status"],
                )
            )

        await session.commit()

    await engine.dispose()

    total_weeks = len(_WEEKS)
    total_txs = sum(len(w["transactions"]) for w in _WEEKS)
    print(f"Seed complete.")
    print(f"  User:         {DEMO_EMAIL} / {DEMO_PASSWORD}")
    print(f"  Weeks:        {total_weeks} ({total_weeks - 1} past + 1 current)")
    print(f"  Transactions: {total_txs}")
    print(f"  Goals:        {len(_GOALS)}")
    print(f"  Opening balance (week 1): €{_FIRST_OPENING}")
    print(f"  Current week opening:     €{current_week_opening}")


if __name__ == "__main__":
    asyncio.run(seed_database())
