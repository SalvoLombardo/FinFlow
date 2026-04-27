import uuid
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from celery_app.tasks.month_setup import (
    _next_month,
    _week_ranges,
    create_next_month_weeks,
)
from celery_app.db import TransactionType


# ── Helper: build a mock SQLAlchemy Session usable as context manager ──────────

def _make_session():
    s = MagicMock()
    s.__enter__ = MagicMock(return_value=s)
    s.__exit__ = MagicMock(return_value=False)
    return s


def _make_query(results):
    """Return a mock query whose .filter().first()/.all() yield results."""
    q = MagicMock()
    q.filter.return_value = q
    q.order_by.return_value = q
    q.join.return_value = q
    q.all.return_value = results if isinstance(results, list) else [results]
    q.first.return_value = results[0] if isinstance(results, list) and results else results
    return q


# ── Pure helper tests ──────────────────────────────────────────────────────────

def test_next_month_regular():
    assert _next_month(date(2026, 4, 27)) == (2026, 5)


def test_next_month_december():
    assert _next_month(date(2026, 12, 1)) == (2027, 1)


def test_week_ranges_may_2026():
    # May 2026: first Monday is May 4
    ranges = _week_ranges(2026, 5)
    assert len(ranges) == 4
    assert ranges[0] == (date(2026, 5, 4), date(2026, 5, 10))
    assert ranges[-1] == (date(2026, 5, 25), date(2026, 5, 31))


def test_week_ranges_all_monday_to_sunday():
    for ws, we in _week_ranges(2026, 5):
        assert ws.weekday() == 0
        assert (we - ws).days == 6


def test_week_ranges_all_within_month():
    for ws, _ in _week_ranges(2026, 5):
        assert ws.month == 5


# ── Task tests ─────────────────────────────────────────────────────────────────

def test_create_next_month_weeks_no_users():
    session = _make_session()
    session.query.return_value = _make_query([])

    mock_self = MagicMock()
    with patch("celery_app.tasks.month_setup.get_session", return_value=session):
        with patch("celery_app.tasks.month_setup._today", return_value=date(2026, 4, 27)):
            result = create_next_month_weeks.run(mock_self)

    assert result["created"] == 0
    assert result["month"] == "2026-05"
    session.commit.assert_called_once()


def test_create_next_month_weeks_new_user_no_previous_weeks():
    user = MagicMock()
    user.id = uuid.uuid4()

    session = _make_session()

    call_count = {"user": 0, "fw": 0, "txn": 0}

    def query_side_effect(model):
        from celery_app.db import User, FinancialWeek, Transaction
        if model is User:
            return _make_query([user])
        if model is FinancialWeek:
            call_count["fw"] += 1
            if call_count["fw"] == 1:
                # last_week query
                return _make_query(None)
            # existence check → no existing week
            return _make_query(None)
        if model is Transaction:
            return _make_query([])
        return MagicMock()

    session.query.side_effect = query_side_effect

    mock_self = MagicMock()
    with patch("celery_app.tasks.month_setup.get_session", return_value=session):
        with patch("celery_app.tasks.month_setup._today", return_value=date(2026, 4, 27)):
            with patch("celery_app.tasks.month_setup._send_audit"):
                result = create_next_month_weeks.run(mock_self)

    # 4 weeks for May 2026
    assert result["created"] == 4
    assert session.add.call_count >= 4  # at least one add per week
    session.commit.assert_called_once()


def test_create_next_month_weeks_uses_closing_balance():
    """First new week opening_balance must equal last_week.closing_balance."""
    user = MagicMock()
    user.id = uuid.uuid4()

    last_week = MagicMock()
    last_week.id = uuid.uuid4()
    last_week.closing_balance = Decimal("1234.56")
    last_week.opening_balance = Decimal("1000.00")

    added_weeks = []
    session = _make_session()
    session.add.side_effect = lambda obj: added_weeks.append(obj)

    fw_call = {"n": 0}

    def query_side_effect(model):
        from celery_app.db import User, FinancialWeek, Transaction
        if model is User:
            return _make_query([user])
        if model is FinancialWeek:
            fw_call["n"] += 1
            if fw_call["n"] == 1:
                return _make_query(last_week)
            return _make_query(None)
        if model is Transaction:
            return _make_query([])
        return MagicMock()

    session.query.side_effect = query_side_effect

    mock_self = MagicMock()
    with patch("celery_app.tasks.month_setup.get_session", return_value=session):
        with patch("celery_app.tasks.month_setup._today", return_value=date(2026, 4, 27)):
            with patch("celery_app.tasks.month_setup._send_audit"):
                create_next_month_weeks.run(mock_self)

    from celery_app.db import FinancialWeek as FW
    new_weeks = [obj for obj in added_weeks if isinstance(obj, FW)]
    assert new_weeks[0].opening_balance == Decimal("1234.56")


def test_create_next_month_weeks_copies_recurring_transactions():
    user = MagicMock()
    user.id = uuid.uuid4()

    last_week = MagicMock()
    last_week.id = uuid.uuid4()
    last_week.closing_balance = Decimal("500.00")

    recurring_txn = MagicMock()
    recurring_txn.name = "Affitto"
    recurring_txn.amount = Decimal("700.00")
    recurring_txn.type = TransactionType.expense
    recurring_txn.category = "Housing"
    recurring_txn.recurrence_rule = "weekly"
    recurring_txn.notes = None

    added_objects = []
    session = _make_session()
    session.add.side_effect = lambda obj: added_objects.append(obj)

    fw_call = {"n": 0}

    def query_side_effect(model):
        from celery_app.db import User, FinancialWeek, Transaction
        if model is User:
            return _make_query([user])
        if model is FinancialWeek:
            fw_call["n"] += 1
            if fw_call["n"] == 1:
                return _make_query(last_week)
            return _make_query(None)
        if model is Transaction:
            return _make_query([recurring_txn])
        return MagicMock()

    session.query.side_effect = query_side_effect

    mock_self = MagicMock()
    with patch("celery_app.tasks.month_setup.get_session", return_value=session):
        with patch("celery_app.tasks.month_setup._today", return_value=date(2026, 4, 27)):
            with patch("celery_app.tasks.month_setup._send_audit"):
                create_next_month_weeks.run(mock_self)

    from celery_app.db import Transaction as Txn
    copied_txns = [obj for obj in added_objects if isinstance(obj, Txn)]
    assert len(copied_txns) == 1
    assert copied_txns[0].name == "Affitto"
    assert copied_txns[0].is_recurring is True


def test_create_next_month_weeks_skips_existing():
    """Weeks that already exist must not be re-created."""
    user = MagicMock()
    user.id = uuid.uuid4()

    existing_week = MagicMock()

    fw_call = {"n": 0}
    session = _make_session()

    def query_side_effect(model):
        from celery_app.db import User, FinancialWeek, Transaction
        if model is User:
            return _make_query([user])
        if model is FinancialWeek:
            fw_call["n"] += 1
            if fw_call["n"] == 1:
                return _make_query(None)
            # All existence checks return an existing week
            return _make_query(existing_week)
        if model is Transaction:
            return _make_query([])
        return MagicMock()

    session.query.side_effect = query_side_effect

    mock_self = MagicMock()
    with patch("celery_app.tasks.month_setup.get_session", return_value=session):
        with patch("celery_app.tasks.month_setup._today", return_value=date(2026, 4, 27)):
            with patch("celery_app.tasks.month_setup._send_audit"):
                result = create_next_month_weeks.run(mock_self)

    assert result["created"] == 0
    session.add.assert_not_called()


def test_create_next_month_weeks_retries_on_db_error():
    session = _make_session()
    session.query.side_effect = RuntimeError("DB connection lost")

    mock_self = MagicMock()
    mock_self.retry.side_effect = RuntimeError("retry")

    with patch("celery_app.tasks.month_setup.get_session", return_value=session):
        with patch("celery_app.tasks.month_setup._today", return_value=date(2026, 4, 27)):
            with pytest.raises(RuntimeError, match="retry"):
                create_next_month_weeks.run(mock_self)

    mock_self.retry.assert_called_once()
