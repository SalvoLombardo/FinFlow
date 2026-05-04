"""Tests for /api/v1/insights and POST /settings/ai/test."""
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.ai_insight import AIInsight
from app.models.user_ai_settings import AIMode, UserAISettings
from tests.conftest import make_mock_result


def _make_insight(user_id: uuid.UUID, is_read: bool = False) -> AIInsight:
    ins = AIInsight()
    ins.id = uuid.uuid4()
    ins.user_id = user_id
    ins.insight_type = "savings_tip"
    ins.content = "Prova a ridurre le spese in Trasporti."
    ins.model_used = "gpt-4o-mini"
    ins.generated_at = datetime(2026, 4, 30, 12, 0, 0)
    ins.is_read = is_read
    return ins


def _make_ai_settings(user_id: uuid.UUID, enabled: bool = True) -> UserAISettings:
    cfg = UserAISettings()
    cfg.id = uuid.uuid4()
    cfg.user_id = user_id
    cfg.ai_enabled = enabled
    cfg.ai_mode = AIMode.api_key
    cfg.ai_provider = "openai"
    cfg.ai_model = "gpt-4o-mini"
    cfg.api_key_enc = "encrypted"
    cfg.ollama_url = "http://localhost:11434"
    cfg.ollama_model = "llama3.2"
    return cfg


# ---------------------------------------------------------------------------
# GET /insights
# ---------------------------------------------------------------------------

def test_list_insights_empty(client, mock_db):
    mock_db.execute.return_value = make_mock_result(scalars_list=[])
    r = client.get("/api/v1/insights/")
    assert r.status_code == 200
    assert r.json() == []


def test_list_insights_returns_all(client, mock_db, test_user):
    insights = [_make_insight(test_user.id), _make_insight(test_user.id)]
    mock_db.execute.return_value = make_mock_result(scalars_list=insights)
    r = client.get("/api/v1/insights/")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_list_insights_pagination_param(client, mock_db):
    mock_db.execute.return_value = make_mock_result(scalars_list=[])
    r = client.get("/api/v1/insights/?page=2&page_size=5")
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# POST /insights  — queue AI analysis
# ---------------------------------------------------------------------------

def test_post_insights_queues_event_when_allowed(client, mock_db):
    with patch("app.api.routes.insights.check_ai_rate_limit", new=AsyncMock(return_value=True)), \
         patch("app.api.routes.insights.sns_publisher.publish", new=AsyncMock()) as mock_pub:
        r = client.post("/api/v1/insights/")
    assert r.status_code == 202
    assert r.json() == {"status": "queued"}
    mock_pub.assert_awaited_once()


def test_post_insights_returns_429_when_rate_limited(client, mock_db):
    with patch("app.api.routes.insights.check_ai_rate_limit", new=AsyncMock(return_value=False)):
        r = client.post("/api/v1/insights/")
    assert r.status_code == 429


def test_post_insights_event_type_is_ai_analysis(client, mock_db):
    captured = {}

    async def _capture(event):
        captured["event"] = event

    with patch("app.api.routes.insights.check_ai_rate_limit", new=AsyncMock(return_value=True)), \
         patch("app.api.routes.insights.sns_publisher.publish", side_effect=_capture):
        client.post("/api/v1/insights/")

    assert captured["event"].event_type == "ai.analysis.requested"


# ---------------------------------------------------------------------------
# PUT /insights/{id}/read
# ---------------------------------------------------------------------------

def test_mark_read_returns_insight(client, mock_db, test_user):
    ins = _make_insight(test_user.id)
    mock_db.execute.return_value = make_mock_result(scalar_one=ins)
    r = client.put(f"/api/v1/insights/{ins.id}/read")
    assert r.status_code == 200
    assert r.json()["is_read"] is True


def test_mark_read_returns_404_when_not_found(client, mock_db):
    mock_db.execute.return_value = make_mock_result(scalar_one=None)
    r = client.put(f"/api/v1/insights/{uuid.uuid4()}/read")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# POST /settings/ai/test
# ---------------------------------------------------------------------------

def test_ai_test_returns_response(client, mock_db, test_user):
    cfg = _make_ai_settings(test_user.id, enabled=True)
    mock_db.execute.return_value = make_mock_result(scalar_one=cfg)

    with patch("app.api.routes.settings.AIService") as mock_ai_cls:
        mock_instance = MagicMock()
        mock_instance.generate_savings_tip = AsyncMock(return_value="Consiglio di risparmio!")
        mock_ai_cls.return_value = mock_instance
        r = client.post("/api/v1/settings/ai/test")

    assert r.status_code == 200
    assert r.json()["response"] == "Consiglio di risparmio!"


def test_ai_test_400_when_ai_disabled(client, mock_db, test_user):
    cfg = _make_ai_settings(test_user.id, enabled=False)
    mock_db.execute.return_value = make_mock_result(scalar_one=cfg)
    r = client.post("/api/v1/settings/ai/test")
    assert r.status_code == 400


def test_ai_test_400_when_no_settings(client, mock_db):
    mock_db.execute.return_value = make_mock_result(scalar_one=None)
    r = client.post("/api/v1/settings/ai/test")
    assert r.status_code == 400


def test_ai_test_502_on_provider_error(client, mock_db, test_user):
    cfg = _make_ai_settings(test_user.id, enabled=True)
    mock_db.execute.return_value = make_mock_result(scalar_one=cfg)

    with patch("app.api.routes.settings.AIService") as mock_ai_cls:
        mock_instance = MagicMock()
        mock_instance.generate_savings_tip = AsyncMock(side_effect=ValueError("bad key"))
        mock_ai_cls.return_value = mock_instance
        r = client.post("/api/v1/settings/ai/test")

    assert r.status_code == 502
