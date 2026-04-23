import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from app.models.transaction import Transaction, TransactionType
from app.models.week import FinancialWeek
from app.services.projection import calculate_projection
from tests.conftest import make_mock_result

FROM_WEEK = date(2024, 1, 1)   # Monday
TO_WEEK = date(2024, 2, 19)    # FROM_WEEK + 7 weeks → 8 slots


def _week(user_id, week_start, opening_balance=Decimal("0"), id=None):
    return FinancialWeek(
        id=id or uuid.uuid4(),
        user_id=user_id,
        week_start=week_start,
        week_end=week_start + timedelta(days=6),
        opening_balance=opening_balance,
        created_at=datetime(2024, 1, 1),
    )


def _tx(user_id, week_id, amount, type_):
    return Transaction(
        id=uuid.uuid4(),
        user_id=user_id,
        week_id=week_id,
        name="item",
        amount=amount,
        type=type_,
        is_recurring=False,
        created_at=datetime(2024, 1, 1),
    )


@pytest.mark.asyncio
async def test_projection_no_weeks_returns_eight_zeros(mock_db, user_id):
    mock_db.execute.return_value = make_mock_result(scalars_list=[])

    with patch("app.services.projection.apply_recurrences", new_callable=AsyncMock):
        result = await calculate_projection(user_id, FROM_WEEK, TO_WEEK, mock_db)

    assert len(result) == 8
    assert all(p.projected_balance == Decimal("0") for p in result)
    assert all(p.week_id is None for p in result)
    assert result[0].week_start == FROM_WEEK
    assert result[7].week_start == TO_WEEK


@pytest.mark.asyncio
async def test_projection_income_only(mock_db, user_id):
    """opening=500, income=1000 → balance 1500; weeks 2-8 carry forward 1500."""
    week = _week(user_id, FROM_WEEK, opening_balance=Decimal("500.00"))
    income = _tx(user_id, week.id, Decimal("1000.00"), TransactionType.income)

    call_count = [0]

    def side_effect(_):
        n = call_count[0]
        call_count[0] += 1
        if n == 0:
            return make_mock_result(scalars_list=[week])
        return make_mock_result(scalars_list=[income] if n == 1 else [])

    mock_db.execute.side_effect = side_effect

    with patch("app.services.projection.apply_recurrences", new_callable=AsyncMock):
        result = await calculate_projection(user_id, FROM_WEEK, TO_WEEK, mock_db)

    assert result[0].projected_balance == Decimal("1500.00")
    assert result[0].week_id == week.id
    for r in result[1:]:
        assert r.projected_balance == Decimal("1500.00")
        assert r.week_id is None


@pytest.mark.asyncio
async def test_projection_income_minus_expense(mock_db, user_id):
    """opening=200, income=1000, expense=600 → balance 600."""
    week = _week(user_id, FROM_WEEK, opening_balance=Decimal("200.00"))
    income = _tx(user_id, week.id, Decimal("1000.00"), TransactionType.income)
    expense = _tx(user_id, week.id, Decimal("600.00"), TransactionType.expense)

    call_count = [0]

    def side_effect(_):
        n = call_count[0]
        call_count[0] += 1
        if n == 0:
            return make_mock_result(scalars_list=[week])
        return make_mock_result(scalars_list=[income, expense] if n == 1 else [])

    mock_db.execute.side_effect = side_effect

    with patch("app.services.projection.apply_recurrences", new_callable=AsyncMock):
        result = await calculate_projection(user_id, FROM_WEEK, TO_WEEK, mock_db)

    assert result[0].projected_balance == Decimal("600.00")


@pytest.mark.asyncio
async def test_projection_empty_week_zero_net(mock_db, user_id):
    """A week with no transactions: balance = opening_balance."""
    week = _week(user_id, FROM_WEEK, opening_balance=Decimal("300.00"))

    call_count = [0]

    def side_effect(_):
        n = call_count[0]
        call_count[0] += 1
        if n == 0:
            return make_mock_result(scalars_list=[week])
        return make_mock_result(scalars_list=[])  # no transactions

    mock_db.execute.side_effect = side_effect

    with patch("app.services.projection.apply_recurrences", new_callable=AsyncMock):
        result = await calculate_projection(user_id, FROM_WEEK, TO_WEEK, mock_db)

    assert result[0].projected_balance == Decimal("300.00")


@pytest.mark.asyncio
async def test_projection_four_consecutive_weeks(mock_db, user_id):
    """
    4 weeks, each opening=100, income=50.
    Each week is independent (opening + net), so each shows 150.
    Weeks 5-8 carry forward 150 (last computed balance).
    """
    weeks = [
        _week(user_id, FROM_WEEK + timedelta(weeks=i), opening_balance=Decimal("100.00"))
        for i in range(4)
    ]
    txs_per_week = [
        [_tx(user_id, w.id, Decimal("50.00"), TransactionType.income)]
        for w in weeks
    ]

    call_count = [0]

    def side_effect(_):
        n = call_count[0]
        call_count[0] += 1
        if n == 0:
            return make_mock_result(scalars_list=weeks)
        if 1 <= n <= 4:
            return make_mock_result(scalars_list=txs_per_week[n - 1])
        return make_mock_result(scalars_list=[])

    mock_db.execute.side_effect = side_effect

    with patch("app.services.projection.apply_recurrences", new_callable=AsyncMock):
        result = await calculate_projection(user_id, FROM_WEEK, TO_WEEK, mock_db)

    assert len(result) == 8
    for i in range(4):
        assert result[i].projected_balance == Decimal("150.00")
        assert result[i].week_id == weeks[i].id
    for i in range(4, 8):
        assert result[i].projected_balance == Decimal("150.00")  # carry-forward
        assert result[i].week_id is None


@pytest.mark.asyncio
async def test_projection_calls_apply_recurrences_for_each_week(mock_db, user_id):
    """apply_recurrences must be called once per existing week."""
    weeks = [
        _week(user_id, FROM_WEEK + timedelta(weeks=i))
        for i in range(3)
    ]

    call_count = [0]

    def side_effect(_):
        n = call_count[0]
        call_count[0] += 1
        if n == 0:
            return make_mock_result(scalars_list=weeks)
        return make_mock_result(scalars_list=[])

    mock_db.execute.side_effect = side_effect

    with patch("app.services.projection.apply_recurrences", new_callable=AsyncMock) as mock_recur:
        await calculate_projection(user_id, FROM_WEEK, TO_WEEK, mock_db)

    assert mock_recur.call_count == 3
