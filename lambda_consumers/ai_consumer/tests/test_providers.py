"""Tests for lambda_consumers/ai_consumer/providers.py — mock each AI SDK."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Ollama
# ---------------------------------------------------------------------------

async def test_call_ollama_posts_to_generate_endpoint():
    import providers

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"response": "ottima settimana!"}

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("providers.httpx.AsyncClient", return_value=mock_ctx):
        result = await providers.call_ollama("http://localhost:11434", "llama3.2", "test prompt")

    assert result == "ottima settimana!"
    mock_client.post.assert_awaited_once()
    url_arg = mock_client.post.call_args[0][0]
    assert "/api/generate" in url_arg


# ---------------------------------------------------------------------------
# OpenAI
# ---------------------------------------------------------------------------

async def test_call_openai_uses_chat_completions():
    import sys
    import providers

    mock_msg = MagicMock()
    mock_msg.content = "Consiglio OpenAI"
    mock_choice = MagicMock()
    mock_choice.message = mock_msg
    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]

    mock_openai_instance = AsyncMock()
    mock_openai_instance.chat.completions.create = AsyncMock(return_value=mock_resp)

    # AsyncOpenAI is imported lazily inside call_openai(); inject the whole module.
    mock_openai_module = MagicMock()
    mock_openai_module.AsyncOpenAI = MagicMock(return_value=mock_openai_instance)

    with patch.dict(sys.modules, {"openai": mock_openai_module}):
        result = await providers.call_openai("fake-key", "gpt-4o-mini", "test prompt")

    assert result == "Consiglio OpenAI"
    mock_openai_instance.chat.completions.create.assert_awaited_once()


# ---------------------------------------------------------------------------
# generate() — routing
# ---------------------------------------------------------------------------

async def test_generate_routes_to_ollama_mode():
    import providers

    with patch("providers.call_ollama", new=AsyncMock(return_value="ollama response")) as mock_ol:
        result = await providers.generate(
            ai_mode="ollama",
            ai_provider=None,
            api_key_enc=None,
            ai_model=None,
            ollama_url="http://localhost:11434",
            ollama_model="llama3.2",
            prompt="test",
        )
    mock_ol.assert_awaited_once()
    assert result == "ollama response"


async def test_generate_raises_for_unknown_provider():
    import providers

    with patch("providers._decrypt_key", return_value="key"), \
         pytest.raises(ValueError, match="Unknown provider"):
        await providers.generate(
            ai_mode="api_key",
            ai_provider="unknown_provider",
            api_key_enc="enc",
            ai_model=None,
            ollama_url="",
            ollama_model="",
            prompt="test",
        )
