"""Tests for lambda_consumers/notification_consumer/handler.py"""
import json
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_sqs_event(
    *,
    goal_name: str = "Vacanza",
    current_amount: str = "700",
    target_amount: str = "1000",
    progress_pct: str = "70.0",
    days_remaining: str = "30",
    msg_id: str = "msg-001",
) -> dict:
    inner = json.dumps({
        "event_type": "goal.progress",
        "user_id": str(uuid.uuid4()),
        "payload": {
            "goal_name": goal_name,
            "current_amount": current_amount,
            "target_amount": target_amount,
            "progress_pct": progress_pct,
            "days_remaining": days_remaining,
        },
    })
    return {"Records": [{"body": json.dumps({"Message": inner}), "messageId": msg_id}]}


def _make_ev(goal_name: str = "Vacanza"):
    import handler as h
    return h.SQSEvent(
        event_type="goal.progress",
        user_id=str(uuid.uuid4()),
        payload={
            "goal_name": goal_name,
            "current_amount": "700",
            "target_amount": "1000",
            "progress_pct": "70.0",
            "days_remaining": "30",
        },
    )


def _make_sns_client_mock():
    """Return (mock_ctx, mock_client) for aioboto3 session.client()."""
    mock_client = AsyncMock()
    mock_client.publish = AsyncMock()
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    return mock_ctx, mock_client


# ---------------------------------------------------------------------------
# lambda_handler — batch processing
# ---------------------------------------------------------------------------

def test_handler_returns_empty_failures_on_success():
    """When NOTIFICATION_TOPIC_ARN is unset, _process logs and returns — no SNS call."""
    import handler as h

    with patch.object(h, "NOTIFICATION_TOPIC_ARN", ""):
        result = h.lambda_handler(_make_sqs_event(), {})

    assert result == {"batchItemFailures": []}


def test_handler_records_failure_on_exception():
    import handler as h

    with patch.object(h, "_process", new=AsyncMock(side_effect=RuntimeError("SNS down"))):
        result = h.lambda_handler(_make_sqs_event(), {})

    assert result["batchItemFailures"] == [{"itemIdentifier": "msg-001"}]


def test_handler_processes_multiple_records():
    import handler as h

    inner = json.dumps({
        "event_type": "goal.progress",
        "user_id": str(uuid.uuid4()),
        "payload": {"goal_name": "Test", "current_amount": "0", "target_amount": "100",
                    "progress_pct": "0", "days_remaining": "10"},
    })
    body = json.dumps({"Message": inner})
    event = {
        "Records": [
            {"body": body, "messageId": "m1"},
            {"body": body, "messageId": "m2"},
        ]
    }
    mock_process = AsyncMock()
    with patch.object(h, "_process", mock_process):
        result = h.lambda_handler(event, {})

    assert result == {"batchItemFailures": []}
    assert mock_process.await_count == 2


# ---------------------------------------------------------------------------
# _process — routing
# ---------------------------------------------------------------------------

async def test_process_does_not_call_send_sns_when_no_topic_arn():
    import handler as h

    ev = _make_ev()
    mock_send = AsyncMock()
    with patch.object(h, "NOTIFICATION_TOPIC_ARN", ""), \
         patch.object(h, "_send_sns", mock_send):
        await h._process(ev)

    mock_send.assert_not_awaited()


async def test_process_calls_send_sns_when_topic_arn_set():
    import handler as h

    ev = _make_ev(goal_name="Fondo emergenza")
    mock_send = AsyncMock()
    with patch.object(h, "NOTIFICATION_TOPIC_ARN", "arn:aws:sns:eu-west-1:123:test"), \
         patch.object(h, "_send_sns", mock_send):
        await h._process(ev)

    mock_send.assert_awaited_once()
    args = mock_send.call_args.args
    assert args[0] == ev.user_id
    assert args[1] == "Fondo emergenza"


async def test_process_message_contains_progress_and_amounts():
    """The formatted message passed to _send_sns must include progress % and amounts."""
    import handler as h

    ev = _make_ev()
    captured = {}

    async def _capture(user_id, goal_name, message):
        captured["message"] = message

    with patch.object(h, "NOTIFICATION_TOPIC_ARN", "arn:aws:sns:eu-west-1:123:test"), \
         patch.object(h, "_send_sns", _capture):
        await h._process(ev)

    msg = captured["message"]
    assert "70.0%" in msg
    assert "700" in msg
    assert "1000" in msg


# ---------------------------------------------------------------------------
# _send_sns — SNS publish
# ---------------------------------------------------------------------------

async def test_send_sns_publishes_to_correct_topic():
    import handler as h

    topic_arn = "arn:aws:sns:eu-west-1:932708080246:finflow-prod-notifications"
    mock_ctx, mock_client = _make_sns_client_mock()

    with patch.object(h, "NOTIFICATION_TOPIC_ARN", topic_arn), \
         patch.object(h._session, "client", return_value=mock_ctx):
        await h._send_sns("user-abc", "Vacanza", "FinFlow alert: needs attention.")

    mock_client.publish.assert_awaited_once()
    call_kwargs = mock_client.publish.call_args.kwargs
    assert call_kwargs["TopicArn"] == topic_arn


async def test_send_sns_subject_contains_goal_name():
    import handler as h

    mock_ctx, mock_client = _make_sns_client_mock()

    with patch.object(h, "NOTIFICATION_TOPIC_ARN", "arn:aws:sns:eu-west-1:123:test"), \
         patch.object(h._session, "client", return_value=mock_ctx):
        await h._send_sns("user-abc", "Fondo emergenza", "alert text")

    call_kwargs = mock_client.publish.call_args.kwargs
    assert "Fondo emergenza" in call_kwargs["Subject"]


async def test_send_sns_includes_user_id_in_message_attributes():
    import handler as h

    user_id = str(uuid.uuid4())
    mock_ctx, mock_client = _make_sns_client_mock()

    with patch.object(h, "NOTIFICATION_TOPIC_ARN", "arn:aws:sns:eu-west-1:123:test"), \
         patch.object(h._session, "client", return_value=mock_ctx):
        await h._send_sns(user_id, "Vacanza", "alert text")

    call_kwargs = mock_client.publish.call_args.kwargs
    assert call_kwargs["MessageAttributes"]["user_id"]["StringValue"] == user_id
