import uuid
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from celery_app.db import GoalStatus
from celery_app.tasks.goal_checker import check_expiring_goals


def _make_session():
    s = MagicMock()
    s.__enter__ = MagicMock(return_value=s)
    s.__exit__ = MagicMock(return_value=False)
    return s


def _make_query(results):
    q = MagicMock()
    q.filter.return_value = q
    q.all.return_value = results
    return q


def _make_goal(
    *,
    target_amount: Decimal,
    current_amount: Decimal,
    target_date: date,
    status: GoalStatus = GoalStatus.active,
) -> MagicMock:
    g = MagicMock()
    g.id = uuid.uuid4()
    g.user_id = uuid.uuid4()
    g.name = "Test Goal"
    g.target_amount = target_amount
    g.current_amount = current_amount
    g.target_date = target_date
    g.status = status
    return g


TODAY = date(2026, 4, 27)


def test_no_expiring_goals():
    session = _make_session()
    session.query.return_value = _make_query([])

    mock_self = MagicMock()
    with patch("celery_app.tasks.goal_checker.get_session", return_value=session):
        with patch("celery_app.tasks.goal_checker._today", return_value=TODAY):
            with patch("celery_app.tasks.goal_checker.publish_event") as mock_pub:
                result = check_expiring_goals.run(mock_self)

    assert result == {"published": 0}
    mock_pub.assert_not_called()


def test_goal_expiring_and_behind_gets_event():
    goal = _make_goal(
        target_amount=Decimal("1000"),
        current_amount=Decimal("700"),  # 30% gap → behind > 20%
        target_date=TODAY + timedelta(days=15),
    )
    session = _make_session()
    session.query.return_value = _make_query([goal])

    mock_self = MagicMock()
    with patch("celery_app.tasks.goal_checker.get_session", return_value=session):
        with patch("celery_app.tasks.goal_checker._today", return_value=TODAY):
            with patch("celery_app.tasks.goal_checker.publish_event") as mock_pub:
                result = check_expiring_goals.run(mock_self)

    assert result == {"published": 1}
    mock_pub.assert_called_once()
    call_kwargs = mock_pub.call_args.kwargs
    assert call_kwargs["event_type"] == "goal.progress"
    assert call_kwargs["payload"]["gap_pct"] == 30.0


def test_goal_on_track_not_published():
    goal = _make_goal(
        target_amount=Decimal("1000"),
        current_amount=Decimal("850"),  # 15% gap → on track (≤ 20%)
        target_date=TODAY + timedelta(days=10),
    )
    session = _make_session()
    session.query.return_value = _make_query([goal])

    mock_self = MagicMock()
    with patch("celery_app.tasks.goal_checker.get_session", return_value=session):
        with patch("celery_app.tasks.goal_checker._today", return_value=TODAY):
            with patch("celery_app.tasks.goal_checker.publish_event") as mock_pub:
                result = check_expiring_goals.run(mock_self)

    assert result == {"published": 0}
    mock_pub.assert_not_called()


def test_goal_exactly_at_threshold_not_published():
    # gap = 20% exactly → NOT published (condition is gap > 20%)
    goal = _make_goal(
        target_amount=Decimal("1000"),
        current_amount=Decimal("800"),
        target_date=TODAY + timedelta(days=5),
    )
    session = _make_session()
    session.query.return_value = _make_query([goal])

    mock_self = MagicMock()
    with patch("celery_app.tasks.goal_checker.get_session", return_value=session):
        with patch("celery_app.tasks.goal_checker._today", return_value=TODAY):
            with patch("celery_app.tasks.goal_checker.publish_event") as mock_pub:
                result = check_expiring_goals.run(mock_self)

    assert result == {"published": 0}


def test_goal_zero_target_amount_skipped():
    goal = _make_goal(
        target_amount=Decimal("0"),
        current_amount=Decimal("0"),
        target_date=TODAY + timedelta(days=5),
    )
    session = _make_session()
    session.query.return_value = _make_query([goal])

    mock_self = MagicMock()
    with patch("celery_app.tasks.goal_checker.get_session", return_value=session):
        with patch("celery_app.tasks.goal_checker._today", return_value=TODAY):
            with patch("celery_app.tasks.goal_checker.publish_event") as mock_pub:
                result = check_expiring_goals.run(mock_self)

    assert result == {"published": 0}


def test_mixed_goals_only_behind_ones_published():
    behind = _make_goal(
        target_amount=Decimal("500"),
        current_amount=Decimal("200"),  # 60% gap
        target_date=TODAY + timedelta(days=20),
    )
    on_track = _make_goal(
        target_amount=Decimal("500"),
        current_amount=Decimal("480"),  # 4% gap
        target_date=TODAY + timedelta(days=20),
    )
    session = _make_session()
    session.query.return_value = _make_query([behind, on_track])

    mock_self = MagicMock()
    with patch("celery_app.tasks.goal_checker.get_session", return_value=session):
        with patch("celery_app.tasks.goal_checker._today", return_value=TODAY):
            with patch("celery_app.tasks.goal_checker.publish_event") as mock_pub:
                result = check_expiring_goals.run(mock_self)

    assert result == {"published": 1}
    assert mock_pub.call_count == 1


def test_check_expiring_retries_on_db_error():
    session = _make_session()
    session.query.side_effect = RuntimeError("DB error")

    mock_self = MagicMock()
    mock_self.retry.side_effect = RuntimeError("retry")

    with patch("celery_app.tasks.goal_checker.get_session", return_value=session):
        with patch("celery_app.tasks.goal_checker._today", return_value=TODAY):
            with pytest.raises(RuntimeError, match="retry"):
                check_expiring_goals.run(mock_self)

    mock_self.retry.assert_called_once()
