"""Tests for backend/app/services/ai/service.py — AIService factory + generate methods."""
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cryptography.fernet import Fernet

from app.models.user_ai_settings import AIMode, UserAISettings
from app.services.ai.service import AIService


def _fernet_key() -> str:
    return Fernet.generate_key().decode()


def _make_settings(mode: AIMode = AIMode.api_key, provider: str = "openai", model: str | None = None) -> UserAISettings:
    s = UserAISettings()
    s.ai_mode = mode
    s.ai_provider = provider
    s.ai_model = model
    s.ollama_url = "http://localhost:11434"
    s.ollama_model = "llama3.2"
    s.api_key_enc = None
    return s


def _encrypt_key(plaintext: str, enc_key: str) -> str:
    return Fernet(enc_key.encode()).encrypt(plaintext.encode()).decode()


# ---------------------------------------------------------------------------
# _decrypt_key
# ---------------------------------------------------------------------------

def test_decrypt_key_roundtrip():
    enc_key = _fernet_key()
    ciphertext = _encrypt_key("sk-test-123", enc_key)

    with patch("app.services.ai.service.settings") as mock_cfg:
        mock_cfg.ENCRYPTION_KEY = enc_key
        plaintext = AIService._decrypt_key(ciphertext)

    assert plaintext == "sk-test-123"


def test_decrypt_key_raises_when_no_ciphertext():
    with pytest.raises(ValueError, match="No API key"):
        AIService._decrypt_key(None)


def test_decrypt_key_raises_when_no_encryption_key():
    with patch("app.services.ai.service.settings") as mock_cfg:
        mock_cfg.ENCRYPTION_KEY = ""
        with pytest.raises(ValueError, match="ENCRYPTION_KEY"):
            AIService._decrypt_key("somecipher")


# ---------------------------------------------------------------------------
# _provider — factory routing
# ---------------------------------------------------------------------------

def test_provider_returns_ollama_for_ollama_mode():
    from app.services.ai.ollama import OllamaProvider
    s = _make_settings(mode=AIMode.ollama)
    service = AIService(s)
    provider = service._provider()
    assert isinstance(provider, OllamaProvider)


def test_provider_returns_openai_for_api_key_mode():
    from app.services.ai.openai_provider import OpenAIProvider
    enc_key = _fernet_key()
    s = _make_settings(mode=AIMode.api_key, provider="openai")
    s.api_key_enc = _encrypt_key("sk-openai-key", enc_key)

    with patch("app.services.ai.service.settings") as mock_cfg:
        mock_cfg.ENCRYPTION_KEY = enc_key
        provider = AIService(s)._provider()

    assert isinstance(provider, OpenAIProvider)


def test_provider_uses_default_model_when_none_set():
    from app.services.ai.openai_provider import OpenAIProvider
    enc_key = _fernet_key()
    s = _make_settings(mode=AIMode.api_key, provider="openai", model=None)
    s.api_key_enc = _encrypt_key("sk-openai-key", enc_key)

    with patch("app.services.ai.service.settings") as mock_cfg:
        mock_cfg.ENCRYPTION_KEY = enc_key
        provider = AIService(s)._provider()

    assert provider._model == "gpt-4o-mini"


def test_provider_raises_for_unknown_provider():
    enc_key = _fernet_key()
    s = _make_settings(mode=AIMode.api_key, provider="unknown_llm")
    s.api_key_enc = _encrypt_key("key", enc_key)

    with patch("app.services.ai.service.settings") as mock_cfg:
        mock_cfg.ENCRYPTION_KEY = enc_key
        with pytest.raises(ValueError, match="Unknown"):
            AIService(s)._provider()


# ---------------------------------------------------------------------------
# generate_weekly_insight
# ---------------------------------------------------------------------------

async def test_generate_weekly_insight_calls_provider():
    s = _make_settings(mode=AIMode.ollama)
    service = AIService(s)

    mock_provider = AsyncMock()
    mock_provider.generate = AsyncMock(return_value="Ottima settimana!")

    with patch.object(service, "_provider", return_value=mock_provider):
        result = await service.generate_weekly_insight(
            week_label="W12",
            opening_balance=1000.0,
            closing_balance=1200.0,
            total_income=500.0,
            total_expense=300.0,
            top_categories=[("Spesa", 200.0), ("Trasporti", 100.0)],
        )

    assert result == "Ottima settimana!"
    mock_provider.generate.assert_awaited_once()


# ---------------------------------------------------------------------------
# generate_savings_tip
# ---------------------------------------------------------------------------

async def test_generate_savings_tip_calls_provider():
    s = _make_settings(mode=AIMode.ollama)
    service = AIService(s)

    mock_provider = AsyncMock()
    mock_provider.generate = AsyncMock(return_value="Risparmia di più!")

    with patch.object(service, "_provider", return_value=mock_provider):
        result = await service.generate_savings_tip(
            avg_weekly_income=800.0,
            avg_weekly_expense=600.0,
            top_categories=[("Ristoranti", 200.0)],
            weeks_analyzed=8,
        )

    assert result == "Risparmia di più!"
    mock_provider.generate.assert_awaited_once()


# ---------------------------------------------------------------------------
# generate_goal_advice
# ---------------------------------------------------------------------------

async def test_generate_goal_advice_calls_provider():
    s = _make_settings(mode=AIMode.ollama)
    service = AIService(s)

    mock_provider = AsyncMock()
    mock_provider.generate = AsyncMock(return_value="Puoi farcela!")

    with patch.object(service, "_provider", return_value=mock_provider):
        result = await service.generate_goal_advice(
            goal_name="Vacanza",
            target_amount=2000.0,
            current_amount=500.0,
            target_date="2026-08-01",
            avg_weekly_savings=50.0,
        )

    assert result == "Puoi farcela!"
    mock_provider.generate.assert_awaited_once()
