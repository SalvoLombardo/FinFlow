"""
Standalone AI provider implementations for the ai_consumer Lambda.
Mirrors backend/app/services/ai/ but with no dependency on the backend package.
"""
import asyncio
import logging
import os
import random

import httpx

logger = logging.getLogger(__name__)

AI_TIMEOUT = 30.0

# Each user configures exactly one provider (no backup provider in the data model,
# and Ollama isn't reachable from Lambda in production), so "fallback" here means
# retrying the configured provider through transient failures rather than switching
# providers. Permanent failures (bad API key, bad request) fail immediately.
MAX_PROVIDER_ATTEMPTS = 3
RETRY_BASE_DELAY = 1.0  # seconds; backoff is RETRY_BASE_DELAY * 2**attempt + jitter

# Exception class names — across httpx, openai, anthropic and google-generativeai —
# that signal a transient failure even when no HTTP status code is attached.
_RETRYABLE_EXCEPTION_NAMES = {
    "APITimeoutError", "APIConnectionError",
    "TimeoutException", "ConnectTimeout", "ReadTimeout", "ConnectError",
    "ServiceUnavailable", "DeadlineExceeded", "ResourceExhausted",
    "InternalServerError", "RetryError", "Aborted",
}

SYSTEM_PROMPT = (
    "Sei un assistente finanziario personale amichevole e pratico. "
    "Dai consigli concreti basati sui dati reali. Rispondi in italiano. "
    "Max 3-4 frasi. Parla come un amico esperto, non come un chatbot."
)


def _decrypt_key(enc: str) -> str:
    from cryptography.fernet import Fernet
    key = os.environ.get("ENCRYPTION_KEY", "")
    if not key:
        raise ValueError("ENCRYPTION_KEY not set")
    return Fernet(key.encode()).decrypt(enc.encode()).decode()


def _status_code(exc: Exception) -> int | None:
    """Best-effort extraction of an HTTP-like status code from any SDK's exception shape."""
    for attr in ("status_code", "code"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
    response = getattr(exc, "response", None)
    if response is not None:
        return getattr(response, "status_code", None)
    return None


def _is_retryable(exc: Exception) -> bool:
    """Transient errors (timeouts, rate limits, 5xx) are worth retrying.

    Permanent errors (invalid/expired API key, bad request, unknown model — typically
    4xx other than 429) are not: retrying them only delays the inevitable failure and
    burns the user's AI quota for nothing.
    """
    code = _status_code(exc)
    if code is not None:
        return code == 429 or code >= 500
    return type(exc).__name__ in _RETRYABLE_EXCEPTION_NAMES


async def _call_with_retry(label: str, func, *args) -> str:
    """Run an AI provider call, retrying transient failures with exponential backoff + jitter."""
    attempt = 1
    while True:
        try:
            return await func(*args)
        except Exception as exc:
            if attempt >= MAX_PROVIDER_ATTEMPTS or not _is_retryable(exc):
                raise
            delay = RETRY_BASE_DELAY * (2 ** (attempt - 1)) + random.uniform(0, 0.5)
            logger.warning(
                "AI provider %s call failed (attempt %d/%d), retrying in %.1fs: %s",
                label, attempt, MAX_PROVIDER_ATTEMPTS, delay, exc,
            )
            await asyncio.sleep(delay)
            attempt += 1


async def call_ollama(url: str, model: str, prompt: str) -> str:
    async with httpx.AsyncClient(timeout=AI_TIMEOUT) as client:
        resp = await client.post(
            f"{url}/api/generate",
            json={"model": model, "prompt": f"{SYSTEM_PROMPT}\n\n{prompt}", "stream": False},
        )
        resp.raise_for_status()
        return resp.json()["response"].strip()


async def call_openai(api_key: str, model: str, prompt: str) -> str:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=api_key)
    resp = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        timeout=AI_TIMEOUT,
    )
    return resp.choices[0].message.content.strip()


async def call_anthropic(api_key: str, model: str, prompt: str) -> str:
    from anthropic import AsyncAnthropic
    client = AsyncAnthropic(api_key=api_key)
    resp = await client.messages.create(
        model=model,
        max_tokens=512,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text.strip()


async def call_gemini(api_key: str, model: str, prompt: str) -> str:
    import google.generativeai as genai
    genai.configure(api_key=api_key)
    gen_model = genai.GenerativeModel(
        model_name=model,
        system_instruction=SYSTEM_PROMPT,
    )
    resp = await gen_model.generate_content_async(prompt)
    return resp.text.strip()


async def generate(
    ai_mode: str,
    ai_provider: str | None,
    api_key_enc: str | None,
    ai_model: str | None,
    ollama_url: str,
    ollama_model: str,
    prompt: str,
) -> str:
    """Route the prompt to the correct provider and return the generated text."""
    _DEFAULT_MODELS = {
        "openai": "gpt-4o-mini",
        "anthropic": "claude-haiku-4-5-20251001",
        "gemini": "gemini-1.5-flash",
    }

    if ai_mode == "ollama":
        return await _call_with_retry("ollama", call_ollama, ollama_url, ollama_model, prompt)

    api_key = _decrypt_key(api_key_enc or "")
    model = ai_model or _DEFAULT_MODELS.get(ai_provider or "", "gpt-4o-mini")

    if ai_provider == "openai":
        return await _call_with_retry("openai", call_openai, api_key, model, prompt)
    if ai_provider == "anthropic":
        return await _call_with_retry("anthropic", call_anthropic, api_key, model, prompt)
    if ai_provider == "gemini":
        return await _call_with_retry("gemini", call_gemini, api_key, model, prompt)
    raise ValueError(f"Unknown provider: {ai_provider!r}")
