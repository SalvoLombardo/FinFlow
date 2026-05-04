"""Tests for lambda_consumers/ai_consumer/handler.py"""
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_sqs_event(event_type: str, payload: dict, msg_id: str = "msg-001") -> dict:
    inner = json.dumps({
        "event_type": event_type,
        "user_id": str(uuid.uuid4()),
        "payload": payload,
    })
    body = json.dumps({"Message": inner})
    return {"Records": [{"body": body, "messageId": msg_id}]}


def _make_session_mock(execute_side_effects: list | None = None) -> AsyncMock:
    """Return an async context manager mock that wraps a session."""
    session = AsyncMock()
    session.commit = AsyncMock()
    if execute_side_effects:
        session.execute = AsyncMock(side_effect=execute_side_effects)
    else:
        session.execute = AsyncMock()

    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)

    factory = MagicMock(return_value=ctx)
    return factory, session


def _make_ai_row(enabled: bool = True) -> MagicMock:
    row = MagicMock()
    row.__getitem__ = lambda self, key: {
        "ai_enabled": enabled,
        "ai_mode": "api_key",
        "ai_provider": "openai",
        "ai_model": "gpt-4o-mini",
        "api_key_enc": "some-enc",
        "ollama_url": "http://localhost:11434",
        "ollama_model": "llama3.2",
    }[key]
    return row


def _make_execute_result(mapping) -> AsyncMock:
    result = MagicMock()
    result.mappings.return_value.one_or_none.return_value = mapping
    result.mappings.return_value.all.return_value = []
    return result


# ---------------------------------------------------------------------------
# lambda_handler — batch processing
# ---------------------------------------------------------------------------

def test_handler_returns_empty_failures_on_success():
    import handler as h

    event = _make_sqs_event("ai.analysis.requested", {"insight_type": "savings_tip"})
    factory, session = _make_session_mock()

    ai_row = _make_ai_row(enabled=False)
    session.execute.return_value = _make_execute_result(ai_row)

    with patch.object(h, "Session", factory):
        result = h.lambda_handler(event, {})

    assert result == {"batchItemFailures": []}


def test_handler_records_failure_on_exception():
    import handler as h

    event = _make_sqs_event("budget.updated", {"week_id": str(uuid.uuid4())})
    factory, session = _make_session_mock()
    session.execute.side_effect = RuntimeError("DB error")

    with patch.object(h, "Session", factory):
        result = h.lambda_handler(event, {})

    assert len(result["batchItemFailures"]) == 1
    assert result["batchItemFailures"][0]["itemIdentifier"] == "msg-001"


# ---------------------------------------------------------------------------
# _process — AI disabled
# ---------------------------------------------------------------------------

async def test_process_skips_when_ai_disabled():
    import handler as h

    ev = h.SQSEvent(
        event_type="ai.analysis.requested",
        user_id=str(uuid.uuid4()),
        payload={"insight_type": "savings_tip"},
    )
    factory, session = _make_session_mock()
    ai_row = _make_ai_row(enabled=False)
    session.execute.return_value = _make_execute_result(ai_row)

    with patch.object(h, "Session", factory):
        await h._process(ev)

    session.commit.assert_not_awaited()


# ---------------------------------------------------------------------------
# _process — successful insight generation
# ---------------------------------------------------------------------------

async def test_process_saves_insight_for_ai_analysis_event():
    import handler as h

    ev = h.SQSEvent(
        event_type="ai.analysis.requested",
        user_id=str(uuid.uuid4()),
        payload={"insight_type": "savings_tip", "trigger": "manual"},
    )
    factory, session = _make_session_mock()
    ai_row = _make_ai_row(enabled=True)

    # First execute: AI settings; subsequent: week data, transactions
    week_result = MagicMock()
    week_result.mappings.return_value.all.return_value = []  # no weeks → short prompt

    session.execute = AsyncMock(side_effect=[
        _make_execute_result(ai_row),
        week_result,          # weeks query
        week_result,          # transactions query (not reached if no weeks)
    ])

    with patch.object(h, "Session", factory), \
         patch("handler.generate", new=AsyncMock(return_value="Ottimo risparmio!")):
        await h._process(ev)

    session.commit.assert_awaited_once()


async def test_process_uses_weekly_prompt_for_budget_updated():
    import handler as h

    week_id = str(uuid.uuid4())
    ev = h.SQSEvent(
        event_type="budget.updated",
        user_id=str(uuid.uuid4()),
        payload={"week_id": week_id},
    )
    factory, session = _make_session_mock()
    ai_row = _make_ai_row(enabled=True)

    # Week data result
    week_row = MagicMock()
    week_row.__getitem__ = lambda self, key: {
        "week_start": "2026-04-28",
        "week_end": "2026-05-04",
        "opening_balance": "3500.00",
    }[key]
    week_db_result = MagicMock()
    week_db_result.mappings.return_value.one_or_none.return_value = week_row

    # Transactions result
    tx_result = MagicMock()
    tx_result.mappings.return_value.all.return_value = []

    insert_result = MagicMock()  # mock for INSERT INTO ai_insights

    session.execute = AsyncMock(side_effect=[
        _make_execute_result(ai_row),
        week_db_result,
        tx_result,
        insert_result,  # INSERT INTO ai_insights
    ])

    captured_prompt = {}

    async def _capture_generate(**kwargs):
        captured_prompt.update(kwargs)
        return "Settimana ottima!"

    with patch.object(h, "Session", factory), \
         patch("handler.generate", side_effect=_capture_generate):
        await h._process(ev)

    assert "Settimana" in captured_prompt.get("prompt", "")
