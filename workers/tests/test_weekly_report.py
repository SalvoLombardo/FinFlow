import uuid
from unittest.mock import MagicMock, patch, call

import pytest

from celery_app.tasks.weekly_report import generate_for_all_users


def _make_session():
    s = MagicMock()
    s.__enter__ = MagicMock(return_value=s)
    s.__exit__ = MagicMock(return_value=False)
    return s


def _make_query(results):
    q = MagicMock()
    q.filter.return_value = q
    q.join.return_value = q
    q.all.return_value = results
    return q


def test_generate_no_ai_users():
    session = _make_session()
    session.query.return_value = _make_query([])

    mock_self = MagicMock()
    with patch("celery_app.tasks.weekly_report.get_session", return_value=session):
        with patch("celery_app.tasks.weekly_report.publish_event") as mock_pub:
            result = generate_for_all_users.run(mock_self)

    assert result == {"published": 0}
    mock_pub.assert_not_called()


def test_generate_publishes_for_each_ai_user():
    users = [MagicMock(id=uuid.uuid4()) for _ in range(3)]

    session = _make_session()
    session.query.return_value = _make_query(users)

    mock_self = MagicMock()
    with patch("celery_app.tasks.weekly_report.get_session", return_value=session):
        with patch("celery_app.tasks.weekly_report.publish_event") as mock_pub:
            result = generate_for_all_users.run(mock_self)

    assert result == {"published": 3}
    assert mock_pub.call_count == 3
    for c in mock_pub.call_args_list:
        assert c.kwargs["event_type"] == "ai.analysis.requested"
        assert c.kwargs["payload"] == {"trigger": "weekly_report"}


def test_generate_event_contains_user_id():
    uid = uuid.uuid4()
    user = MagicMock(id=uid)

    session = _make_session()
    session.query.return_value = _make_query([user])

    mock_self = MagicMock()
    with patch("celery_app.tasks.weekly_report.get_session", return_value=session):
        with patch("celery_app.tasks.weekly_report.publish_event") as mock_pub:
            generate_for_all_users.run(mock_self)

    assert mock_pub.call_args.kwargs["user_id"] == str(uid)


def test_generate_retries_on_db_error():
    session = _make_session()
    session.query.side_effect = RuntimeError("DB down")

    mock_self = MagicMock()
    mock_self.retry.side_effect = RuntimeError("retry")

    with patch("celery_app.tasks.weekly_report.get_session", return_value=session):
        with pytest.raises(RuntimeError, match="retry"):
            generate_for_all_users.run(mock_self)

    mock_self.retry.assert_called_once()
