"""Tests for services/projection.py — pure functions + calculate_projection."""
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.transaction import Transaction, TransactionType
from app.models.week import FinancialWeek
from app.services.projection import (
    WeekSummaryData,
    _net,
    _parse_rule,
    _should_apply_in_week,
    calculate_projection,
)
from app.services.weeks import week_monday
from tests.conftest import make_mock_result


# ---------------------------------------------------------------------------
# _parse_rule — pure function
# ---------------------------------------------------------------------------

def test_parse_rule_none_defaults_to_weekly():
    assert _parse_rule(None) == ("W", 1)


def test_parse_rule_parses_weekly_interval():
    assert _parse_rule("W:2") == ("W", 2)


def test_parse_rule_parses_monthly():
    assert _parse_rule("M:3") == ("M", 3)


def test_parse_rule_invalid_string_defaults_to_weekly():
    assert _parse_rule("invalid") == ("W", 1)
    assert _parse_rule("X:5") == ("W", 1)
    assert _parse_rule("W:notanumber") == ("W", 1)


# ---------------------------------------------------------------------------
# _net — pure function
# ---------------------------------------------------------------------------

def _make_tx(amount: str, type_: TransactionType) -> Transaction:
    tx = Transaction()
    tx.amount = Decimal(amount)
    tx.type = type_
    return tx


def test_net_income_and_expense():
    txs = [
        _make_tx("1000", TransactionType.income),
        _make_tx("600", TransactionType.expense),
    ]
    income, expense, net = _net(txs)
    assert income == Decimal("1000")
    assert expense == Decimal("600")
    assert net == Decimal("400")


def test_net_empty_list():
    assert _net([]) == (Decimal("0"), Decimal("0"), Decimal("0"))


# ---------------------------------------------------------------------------
# _should_apply_in_week — pure function
# ---------------------------------------------------------------------------

def _make_recurring(rule: str | None, origin: date) -> Transaction:
    tx = Transaction()
    tx.recurrence_rule = rule
    tx.transaction_date = origin
    tx.created_at = datetime(origin.year, origin.month, origin.day)
    tx.recurrence_end_date = None
    return tx


def test_should_apply_weekly_one_week_after_origin():
    monday = week_monday(date(2024, 1, 8))    # known Monday
    origin = monday - timedelta(weeks=1)
    tx = _make_recurring("W:1", origin)
    assert _should_apply_in_week(tx, monday) is True


def test_should_apply_weekly_same_week_is_false():
    monday = week_monday(date(2024, 1, 8))
    tx = _make_recurring("W:1", monday)
    assert _should_apply_in_week(tx, monday) is False


def test_should_apply_biweekly_one_week_is_false():
    monday = week_monday(date(2024, 1, 8))
    origin = monday - timedelta(weeks=1)
    tx = _make_recurring("W:2", origin)
    assert _should_apply_in_week(tx, monday) is False


def test_should_apply_biweekly_two_weeks_is_true():
    monday = week_monday(date(2024, 1, 8))
    origin = monday - timedelta(weeks=2)
    tx = _make_recurring("W:2", origin)
    assert _should_apply_in_week(tx, monday) is True


def test_should_apply_with_past_end_date_is_false():
    monday = week_monday(date(2024, 1, 8))
    origin = monday - timedelta(weeks=1)
    tx = _make_recurring("W:1", origin)
    tx.recurrence_end_date = monday - timedelta(days=1)
    assert _should_apply_in_week(tx, monday) is False


# ---------------------------------------------------------------------------
# calculate_projection — integration with mocked DB
# ---------------------------------------------------------------------------

async def test_projection_returns_one_slot_for_zero_range(mock_db, user_id):
    """n_back=0, n_forward=0, no DB weeks → 1 slot, all virtual."""
    ufs = MagicMock()
    ufs.initial_balance = Decimal("500")

    mock_db.execute = AsyncMock(side_effect=[
        make_mock_result(scalars_list=[]),  # weeks in range
        make_mock_result(scalar_one=None),  # last week anchor
        make_mock_result(scalar_one=ufs),   # get_initial_balance
        make_mock_result(scalars_list=[]),  # recurring txs
    ])

    result = await calculate_projection(user_id, 0, 0, mock_db)

    assert len(result) == 1
    assert result[0].is_projected is False      # current week is never projected
    assert result[0].week_id is None            # no DB record
    assert result[0].opening_balance == Decimal("500")
    assert result[0].closing_balance == Decimal("500")


async def test_projection_week_in_db_uses_real_transactions(mock_db, user_id):
    """A week present in DB uses real transactions, not projected."""
    current_monday = week_monday(date.today())
    week = FinancialWeek(
        id=uuid.uuid4(),
        user_id=user_id,
        week_start=current_monday,
        week_end=current_monday + timedelta(days=6),
        opening_balance=Decimal("1000"),
    )
    income = Transaction()
    income.id = uuid.uuid4()
    income.week_id = week.id
    income.amount = Decimal("500")
    income.type = TransactionType.income

    ufs = MagicMock()
    ufs.initial_balance = Decimal("0")

    mock_db.execute = AsyncMock(side_effect=[
        make_mock_result(scalars_list=[week]),  # weeks in range (current week found)
        make_mock_result(scalar_one=None),       # last week before range
        make_mock_result(scalar_one=ufs),        # get_initial_balance
        make_mock_result(scalars_list=[]),       # recurring txs
        make_mock_result(scalars_list=[income]), # _fetch_transactions for the week
    ])

    result = await calculate_projection(user_id, 0, 0, mock_db)

    assert len(result) == 1
    assert result[0].week_id == week.id
    assert result[0].is_projected is False
    assert result[0].total_income == Decimal("500")
    assert result[0].closing_balance == Decimal("1500")


async def test_projection_three_slots_for_one_past_one_future(mock_db, user_id):
    """n_back=1, n_forward=1 → 3 slots total."""
    ufs = MagicMock()
    ufs.initial_balance = Decimal("0")

    mock_db.execute = AsyncMock(side_effect=[
        make_mock_result(scalars_list=[]),  # weeks (none in DB)
        make_mock_result(scalar_one=None),  # last week before range
        make_mock_result(scalar_one=ufs),   # get_initial_balance
        make_mock_result(scalars_list=[]),  # recurring txs
    ])

    result = await calculate_projection(user_id, 1, 1, mock_db)

    assert len(result) == 3
    past, current, future = result
    assert past.is_projected is False      # past missing week: not projected
    assert current.is_projected is False   # current week: never projected
    assert future.is_projected is True     # future: projected
    # Weeks are consecutive Mondays
    assert past.week_start + timedelta(weeks=1) == current.week_start
    assert current.week_start + timedelta(weeks=1) == future.week_start
