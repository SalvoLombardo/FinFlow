"""Tests for lambda_consumers/ai_consumer/providers.py — mock each AI SDK."""
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
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


# ---------------------------------------------------------------------------
# Error classification — _status_code / _is_retryable
# ---------------------------------------------------------------------------

class _FakeStatusError(Exception):
    def __init__(self, status_code):
        super().__init__(f"status {status_code}")
        self.status_code = status_code


class _FakeResponseError(Exception):
    def __init__(self, status_code):
        super().__init__(f"response status {status_code}")
        self.response = MagicMock(status_code=status_code)


def _named(name: str) -> Exception:
    """Build an exception instance whose class name matches a known SDK error type."""
    return type(name, (Exception,), {})()


@pytest.mark.parametrize("status_code,expected", [
    (429, True),   # rate limited — retry
    (500, True),   # server error — retry
    (503, True),   # service unavailable — retry
    (400, False),  # bad request — permanent
    (401, False),  # invalid API key — permanent
    (403, False),  # forbidden — permanent
])
def test_is_retryable_classifies_status_codes(status_code, expected):
    import providers

    assert providers._is_retryable(_FakeStatusError(status_code)) is expected
    assert providers._is_retryable(_FakeResponseError(status_code)) is expected


@pytest.mark.parametrize("name,expected", [
    ("APITimeoutError", True),
    ("APIConnectionError", True),
    ("ServiceUnavailable", True),
    ("ResourceExhausted", True),
    ("AuthenticationError", False),
    ("InvalidArgument", False),
    ("BadRequestError", False),
])
def test_is_retryable_classifies_known_exception_names(name, expected):
    import providers

    assert providers._is_retryable(_named(name)) is expected


def test_is_retryable_classifies_httpx_exceptions():
    import providers

    assert providers._is_retryable(httpx.TimeoutException("timed out")) is True
    assert providers._is_retryable(httpx.ConnectError("conn refused")) is True


# ---------------------------------------------------------------------------
# _call_with_retry — the actual retry loop
# ---------------------------------------------------------------------------

async def test_call_with_retry_retries_transient_then_succeeds():
    import providers

    func = AsyncMock(side_effect=[_FakeStatusError(503), "ok"])

    with patch("providers.asyncio.sleep", new=AsyncMock()) as mock_sleep:
        result = await providers._call_with_retry("openai", func, "arg")

    assert result == "ok"
    assert func.await_count == 2
    mock_sleep.assert_awaited_once()


async def test_call_with_retry_does_not_retry_permanent_errors():
    import providers

    func = AsyncMock(side_effect=_FakeStatusError(401))

    with patch("providers.asyncio.sleep", new=AsyncMock()) as mock_sleep, \
         pytest.raises(_FakeStatusError):
        await providers._call_with_retry("openai", func, "arg")

    assert func.await_count == 1
    mock_sleep.assert_not_called()


async def test_call_with_retry_gives_up_after_max_attempts():
    import providers

    func = AsyncMock(side_effect=_FakeStatusError(500))

    with patch("providers.asyncio.sleep", new=AsyncMock()), \
         pytest.raises(_FakeStatusError):
        await providers._call_with_retry("anthropic", func, "arg")

    assert func.await_count == providers.MAX_PROVIDER_ATTEMPTS


async def test_generate_retries_through_call_with_retry():
    """generate() must route provider calls through the retry wrapper, not call them directly."""
    import providers

    flaky = AsyncMock(side_effect=[_FakeStatusError(429), "consiglio finale"])

    with patch("providers.call_openai", new=flaky), \
         patch("providers._decrypt_key", return_value="key"), \
         patch("providers.asyncio.sleep", new=AsyncMock()):
        result = await providers.generate(
            ai_mode="api_key",
            ai_provider="openai",
            api_key_enc="enc",
            ai_model="gpt-4o-mini",
            ollama_url="",
            ollama_model="",
            prompt="test",
        )

    assert result == "consiglio finale"
    assert flaky.await_count == 2


# ---------------------------------------------------------------------------
# _decrypt_key — error clarity
# ---------------------------------------------------------------------------

def test_decrypt_key_wraps_invalid_token_with_descriptive_error():
    import providers
    from cryptography.fernet import Fernet

    encrypted_with = Fernet.generate_key()
    decrypted_with = Fernet.generate_key()
    token = Fernet(encrypted_with).encrypt(b"sk-some-api-key").decode()

    with patch("deps.get_secret", return_value=decrypted_with.decode()):
        with pytest.raises(providers.AIKeyDecryptionError, match="ENCRYPTION_KEY"):
            providers._decrypt_key(token)


def test_decrypt_key_succeeds_with_matching_key():
    import providers
    from cryptography.fernet import Fernet

    key = Fernet.generate_key()
    token = Fernet(key).encrypt(b"sk-some-api-key").decode()

    with patch("deps.get_secret", return_value=key.decode()):
        assert providers._decrypt_key(token) == "sk-some-api-key"
