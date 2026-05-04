try:
    from openai import AsyncOpenAI
except ImportError:
    AsyncOpenAI = None  # type: ignore[assignment,misc]


class OpenAIProvider:
    def __init__(self, api_key: str, model: str) -> None:
        if AsyncOpenAI is None:
            raise ImportError("openai package not available in this environment")
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model

    async def generate(self, prompt: str, system: str) -> str:
        resp = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            max_tokens=300,
        )
        return resp.choices[0].message.content or ""
