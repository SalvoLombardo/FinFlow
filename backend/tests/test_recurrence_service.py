import uuid
from datetime import date, datetime
from decimal import Decimal

import pytest

from app.models.transaction import Transaction, TransactionType
from app.models.week import FinancialWeek
from app.services.recurrence import apply_recurrences
from tests.conftest import make_mock_result


def _week(user_id, week_start, id=None):
    return FinancialWeek(
        id=id or uuid.uuid4(),
        user_id=user_id,
        week_start=week_start,
        week_end=week_start,
        opening_balance=Decimal("0"),
        created_at=datetime(2024, 1, 1),
    )


def _tx(user_id, week_id, name, amount, type_=TransactionType.expense, recurring=True):
    return Transaction(
        id=uuid.uuid4(),
        user_id=user_id,
        week_id=week_id,
        name=name,
        amount=amount,
        type=type_,
        is_recurring=recurring,
        created_at=datetime(2024, 1, 1),
    )


@pytest.mark.asyncio
async def test_returns_early_when_week_not_found(mock_db, user_id):
    mock_db.execute.return_value = make_mock_result(scalar_one=None)
    await apply_recurrences(uuid.uuid4(), user_id, mock_db)
    mock_db.add.assert_not_called()


@pytest.mark.asyncio
async def test_returns_early_when_no_previous_week(mock_db, user_id):
    week = _week(user_id, date(2024, 1, 15))
    mock_db.execute.side_effect = [
        make_mock_result(scalar_one=week),
        make_mock_result(scalar_one=None),  # no prev week
    ]
    await apply_recurrences(week.id, user_id, mock_db)
    mock_db.add.assert_not_called()


@pytest.mark.asyncio
async def test_returns_early_when_no_recurring_txs(mock_db, user_id):
    week = _week(user_id, date(2024, 1, 15))
    prev = _week(user_id, date(2024, 1, 8))
    mock_db.execute.side_effect = [
        make_mock_result(scalar_one=week),
        make_mock_result(scalar_one=prev),
        make_mock_result(scalars_list=[]),  # no recurring txs
    ]
    await apply_recurrences(week.id, user_id, mock_db)
    mock_db.add.assert_not_called()


@pytest.mark.asyncio
async def test_copies_recurring_transactions_to_current_week(mock_db, user_id):
    week = _week(user_id, date(2024, 1, 15))
    prev = _week(user_id, date(2024, 1, 8))
    recurring = _tx(user_id, prev.id, "Netflix", Decimal("15.99"))

    mock_db.execute.side_effect = [
        make_mock_result(scalar_one=week),
        make_mock_result(scalar_one=prev),
        make_mock_result(scalars_list=[recurring]),
        make_mock_result(rows=[]),  # no existing names in current week
    ]
    await apply_recurrences(week.id, user_id, mock_db)

    mock_db.add.assert_called_once()
    new_tx: Transaction = mock_db.add.call_args[0][0]
    assert new_tx.name == "Netflix"
    assert new_tx.amount == Decimal("15.99")
    assert new_tx.week_id == week.id
    assert new_tx.is_recurring is True


@pytest.mark.asyncio
async def test_does_not_duplicate_already_present_transaction(mock_db, user_id):
    week = _week(user_id, date(2024, 1, 15))
    prev = _week(user_id, date(2024, 1, 8))
    recurring = _tx(user_id, prev.id, "Netflix", Decimal("15.99"))

    mock_db.execute.side_effect = [
        make_mock_result(scalar_one=week),
        make_mock_result(scalar_one=prev),
        make_mock_result(scalars_list=[recurring]),
        make_mock_result(rows=[("Netflix",)]),  # already in current week
    ]
    await apply_recurrences(week.id, user_id, mock_db)
    mock_db.add.assert_not_called()


@pytest.mark.asyncio
async def test_copies_only_missing_transactions(mock_db, user_id):
    """Two recurring txs, one already present → only the missing one is copied."""
    week = _week(user_id, date(2024, 1, 15))
    prev = _week(user_id, date(2024, 1, 8))
    tx_netflix = _tx(user_id, prev.id, "Netflix", Decimal("15.99"))
    tx_gym = _tx(user_id, prev.id, "Gym", Decimal("30.00"))

    mock_db.execute.side_effect = [
        make_mock_result(scalar_one=week),
        make_mock_result(scalar_one=prev),
        make_mock_result(scalars_list=[tx_netflix, tx_gym]),
        make_mock_result(rows=[("Netflix",)]),  # Netflix already present
    ]
    await apply_recurrences(week.id, user_id, mock_db)

    assert mock_db.add.call_count == 1
    copied: Transaction = mock_db.add.call_args[0][0]
    assert copied.name == "Gym"
