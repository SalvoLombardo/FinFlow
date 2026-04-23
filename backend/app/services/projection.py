from typing import Any

# Phase 1.5: full implementation


async def calculate_projection(user_id: str, from_week: Any, to_week: Any, db: Any) -> list:
    """
    1. Load opening_balance of first week
    2. For each week: sum incomes, subtract expenses, compute closing_balance
    3. Auto-apply recurring transactions if not present
    4. Return list[WeekProjection]
    """
    raise NotImplementedError("Implement in Phase 1.5")
