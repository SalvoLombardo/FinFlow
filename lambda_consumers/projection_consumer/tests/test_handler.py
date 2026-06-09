"""Tests for lambda_consumers/projection_consumer/handler.py"""
import json
import uuid
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_sqs_event(user_id: str = None, msg_id: str = "msg-001") -> dict:
    inner = json.dumps({
        "event_type": "budget.updated",
        "user_id": user_id or str(uuid.uuid4()),
        "payload": {},
    })
    return {"Records": [{"body": json.dumps({"Message": inner}), "messageId": msg_id}]}


def _make_session_mock():
    session = AsyncMock()
    session.commit = AsyncMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return MagicMock(return_value=ctx), session


def _rows(rows: list):
    """Execute result consumed via .mappings().all()."""
    r = MagicMock()
    r.mappings.return_value.all.return_value = rows
    return r


def _one(row):
    """Execute result consumed via .mappings().one_or_none()."""
    r = MagicMock()
    r.mappings.return_value.one_or_none.return_value = row
    return r


def _current_week_start() -> date:
    today = date.today()
    return today - timedelta(days=today.weekday())


# ---------------------------------------------------------------------------
# lambda_handler — batch processing
# ---------------------------------------------------------------------------

def test_handler_returns_empty_failures_on_success():
    import handler as h

    factory, session = _make_session_mock()
    # Minimal path: no weeks, no goals.
    # Execute sequence: SELECT weeks, SELECT initial_balance (fallback), SELECT goals.
    session.execute = AsyncMock(side_effect=[
        _rows([]),
        _one({"initial_balance": "0"}),
        _rows([]),
    ])
    with patch.object(h, "Session", factory):
        result = h.lambda_handler(_make_sqs_event(), {})

    assert result == {"batchItemFailures": []}
    session.commit.assert_awaited_once()


def test_handler_records_failure_on_exception():
    import handler as h

    factory, session = _make_session_mock()
    session.execute = AsyncMock(side_effect=RuntimeError("DB down"))
    with patch.object(h, "Session", factory):
        result = h.lambda_handler(_make_sqs_event(), {})

    assert result["batchItemFailures"] == [{"itemIdentifier": "msg-001"}]
    session.commit.assert_not_awaited()


def test_handler_processes_multiple_records_independently():
    import handler as h

    uid = str(uuid.uuid4())
    inner = json.dumps({"event_type": "budget.updated", "user_id": uid, "payload": {}})
    body = json.dumps({"Message": inner})
    event = {
        "Records": [
            {"body": body, "messageId": "m1"},
            {"body": body, "messageId": "m2"},
        ]
    }
    factory, session = _make_session_mock()
    # Two records × three executes each (weeks, initial_balance, goals).
    session.execute = AsyncMock(side_effect=[
        _rows([]), _one({"initial_balance": "0"}), _rows([]),
        _rows([]), _one({"initial_balance": "0"}), _rows([]),
    ])
    with patch.object(h, "Session", factory):
        result = h.lambda_handler(event, {})

    assert result == {"batchItemFailures": []}
    assert session.commit.await_count == 2


# ---------------------------------------------------------------------------
# _process — closing_balance recomputation
# ---------------------------------------------------------------------------

async def test_process_computes_closing_balance_with_income():
    """opening_balance + income → correct closing_balance in the UPDATE."""
    import handler as h

    week_id = uuid.uuid4()
    ws = _current_week_start()
    ev = h.SQSEvent(event_type="budget.updated", user_id=str(uuid.uuid4()), payload={})
    factory, session = _make_session_mock()
    # Execute sequence:
    # 1. SELECT weeks          → one week (current week)
    # 2. SELECT transactions   → one income tx  (loop: compute net)
    # 3. UPDATE closing_balance
    # 4. SELECT transactions   → same tx again  (current_balance derivation)
    # 5. SELECT goals          → empty
    session.execute = AsyncMock(side_effect=[
        _rows([{"id": week_id, "week_start": ws, "opening_balance": "1000.00"}]),
        _rows([{"amount": "200.00", "type": "income"}]),
        MagicMock(),
        _rows([{"amount": "200.00", "type": "income"}]),
        _rows([]),
    ])
    with patch.object(h, "Session", factory):
        await h._process(ev)

    cb_calls = [
        c for c in session.execute.call_args_list
        if len(c.args) > 1 and isinstance(c.args[1], dict) and "cb" in c.args[1]
    ]
    assert len(cb_calls) == 1
    assert cb_calls[0].args[1]["cb"] == Decimal("1200.00")
    assert cb_calls[0].args[1]["wid"] == week_id


async def test_process_computes_closing_balance_with_expense():
    """opening_balance − expense → correct closing_balance."""
    import handler as h

    week_id = uuid.uuid4()
    ws = _current_week_start()
    ev = h.SQSEvent(event_type="budget.updated", user_id=str(uuid.uuid4()), payload={})
    factory, session = _make_session_mock()
    session.execute = AsyncMock(side_effect=[
        _rows([{"id": week_id, "week_start": ws, "opening_balance": "1000.00"}]),
        _rows([{"amount": "300.00", "type": "expense"}]),
        MagicMock(),
        _rows([{"amount": "300.00", "type": "expense"}]),
        _rows([]),
    ])
    with patch.object(h, "Session", factory):
        await h._process(ev)

    cb_calls = [
        c for c in session.execute.call_args_list
        if len(c.args) > 1 and isinstance(c.args[1], dict) and "cb" in c.args[1]
    ]
    assert cb_calls[0].args[1]["cb"] == Decimal("700.00")


# ---------------------------------------------------------------------------
# _process — current_balance derivation
# ---------------------------------------------------------------------------

async def test_process_falls_back_to_initial_balance_when_no_current_week():
    """A week outside the current week-start means no current_week → use initial_balance."""
    import handler as h

    past_ws = _current_week_start() - timedelta(weeks=1)
    ev = h.SQSEvent(event_type="budget.updated", user_id=str(uuid.uuid4()), payload={})
    factory, session = _make_session_mock()
    # Execute sequence:
    # 1. SELECT weeks  → past week only (not current)
    # 2. SELECT txs    → empty  (loop)
    # 3. UPDATE closing_balance
    # 4. SELECT initial_balance (fallback — no current_week found)
    # 5. SELECT goals  → empty
    session.execute = AsyncMock(side_effect=[
        _rows([{"id": uuid.uuid4(), "week_start": past_ws, "opening_balance": "800.00"}]),
        _rows([]),
        MagicMock(),
        _one({"initial_balance": "999.99"}),
        _rows([]),
    ])
    with patch.object(h, "Session", factory):
        await h._process(ev)

    session.commit.assert_awaited_once()


async def test_process_uses_zero_when_no_settings_row():
    """No initial_balance row → current_balance defaults to 0, no crash."""
    import handler as h

    ev = h.SQSEvent(event_type="budget.updated", user_id=str(uuid.uuid4()), payload={})
    factory, session = _make_session_mock()
    session.execute = AsyncMock(side_effect=[
        _rows([]),
        _one(None),
        _rows([]),
    ])
    with patch.object(h, "Session", factory):
        await h._process(ev)

    session.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# _process — goal updates
# ---------------------------------------------------------------------------

async def test_process_updates_liquidity_goal_with_current_balance():
    """goal_type=liquidity → current_amount equals current_balance directly."""
    import handler as h

    goal_id = uuid.uuid4()
    ev = h.SQSEvent(event_type="budget.updated", user_id=str(uuid.uuid4()), payload={})
    factory, session = _make_session_mock()
    session.execute = AsyncMock(side_effect=[
        _rows([]),
        _one({"initial_balance": "2000.00"}),
        _rows([{
            "id": goal_id,
            "target_amount": "5000.00",
            "goal_type": "liquidity",
            "baseline_balance": None,
        }]),
        MagicMock(),  # UPDATE current_amount (target not yet met)
    ])
    with patch.object(h, "Session", factory):
        await h._process(ev)

    ca_calls = [
        c for c in session.execute.call_args_list
        if len(c.args) > 1 and isinstance(c.args[1], dict) and "ca" in c.args[1]
    ]
    assert len(ca_calls) == 1
    assert ca_calls[0].args[1]["ca"] == Decimal("2000.00")
    assert ca_calls[0].args[1]["gid"] == goal_id


async def test_process_updates_savings_goal_as_balance_minus_baseline():
    """goal_type=savings → current_amount = max(balance − baseline, 0)."""
    import handler as h

    goal_id = uuid.uuid4()
    ev = h.SQSEvent(event_type="budget.updated", user_id=str(uuid.uuid4()), payload={})
    factory, session = _make_session_mock()
    session.execute = AsyncMock(side_effect=[
        _rows([]),
        _one({"initial_balance": "3000.00"}),
        _rows([{
            "id": goal_id,
            "target_amount": "500.00",
            "goal_type": "savings",
            "baseline_balance": "2000.00",
        }]),
        MagicMock(),  # UPDATE current_amount
        MagicMock(),  # UPDATE status=achieved (3000-2000=1000 >= 500)
    ])
    with patch.object(h, "Session", factory):
        await h._process(ev)

    ca_calls = [
        c for c in session.execute.call_args_list
        if len(c.args) > 1 and isinstance(c.args[1], dict) and "ca" in c.args[1]
    ]
    assert ca_calls[0].args[1]["ca"] == Decimal("1000.00")


async def test_process_savings_goal_clamped_to_zero_when_below_baseline():
    """balance < baseline → current_amount = 0 (not negative)."""
    import handler as h

    goal_id = uuid.uuid4()
    ev = h.SQSEvent(event_type="budget.updated", user_id=str(uuid.uuid4()), payload={})
    factory, session = _make_session_mock()
    session.execute = AsyncMock(side_effect=[
        _rows([]),
        _one({"initial_balance": "1500.00"}),
        _rows([{
            "id": goal_id,
            "target_amount": "1000.00",
            "goal_type": "savings",
            "baseline_balance": "2000.00",
        }]),
        MagicMock(),
    ])
    with patch.object(h, "Session", factory):
        await h._process(ev)

    ca_calls = [
        c for c in session.execute.call_args_list
        if len(c.args) > 1 and isinstance(c.args[1], dict) and "ca" in c.args[1]
    ]
    assert ca_calls[0].args[1]["ca"] == Decimal("0")


async def test_process_marks_goal_achieved_when_current_amount_meets_target():
    import handler as h

    goal_id = uuid.uuid4()
    ev = h.SQSEvent(event_type="budget.updated", user_id=str(uuid.uuid4()), payload={})
    factory, session = _make_session_mock()
    session.execute = AsyncMock(side_effect=[
        _rows([]),
        _one({"initial_balance": "1000.00"}),
        _rows([{
            "id": goal_id,
            "target_amount": "1000.00",
            "goal_type": "liquidity",
            "baseline_balance": None,
        }]),
        MagicMock(),  # UPDATE current_amount
        MagicMock(),  # UPDATE status='achieved'
    ])
    with patch.object(h, "Session", factory):
        await h._process(ev)

    # There must be exactly one execute call with gid but without ca (the achieved update).
    gid_only_calls = [
        c for c in session.execute.call_args_list
        if len(c.args) > 1
        and isinstance(c.args[1], dict)
        and "gid" in c.args[1]
        and "ca" not in c.args[1]
    ]
    assert len(gid_only_calls) == 1


async def test_process_does_not_mark_goal_achieved_when_below_target():
    import handler as h

    goal_id = uuid.uuid4()
    ev = h.SQSEvent(event_type="budget.updated", user_id=str(uuid.uuid4()), payload={})
    factory, session = _make_session_mock()
    session.execute = AsyncMock(side_effect=[
        _rows([]),
        _one({"initial_balance": "500.00"}),
        _rows([{
            "id": goal_id,
            "target_amount": "1000.00",
            "goal_type": "liquidity",
            "baseline_balance": None,
        }]),
        MagicMock(),  # UPDATE current_amount only — no achieved update
    ])
    with patch.object(h, "Session", factory):
        await h._process(ev)

    gid_only_calls = [
        c for c in session.execute.call_args_list
        if len(c.args) > 1
        and isinstance(c.args[1], dict)
        and "gid" in c.args[1]
        and "ca" not in c.args[1]
    ]
    assert len(gid_only_calls) == 0
