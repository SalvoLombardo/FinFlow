"""
Standalone AI provider implementations for the ai_consumer Lambda.
Mirrors backend/app/services/ai/ but with no dependency on the backend package.
"""
import os

import httpx

AI_TIMEOUT = 30.0

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
        return await call_ollama(ollama_url, ollama_model, prompt)

    api_key = _decrypt_key(api_key_enc or "")
    model = ai_model or _DEFAULT_MODELS.get(ai_provider or "", "gpt-4o-mini")

    if ai_provider == "openai":
        return await call_openai(api_key, model, prompt)
    if ai_provider == "anthropic":
        return await call_anthropic(api_key, model, prompt)
    if ai_provider == "gemini":
        return await call_gemini(api_key, model, prompt)
    raise ValueError(f"Unknown provider: {ai_provider!r}")
