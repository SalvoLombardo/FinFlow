try:
    import anthropic
except ImportError:
    anthropic = None  # type: ignore[assignment]


class AnthropicProvider:
    def __init__(self, api_key: str, model: str) -> None:
        if anthropic is None:
            raise ImportError("anthropic package not available in this environment")
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model

    async def generate(self, prompt: str, system: str) -> str:
        msg = await self._client.messages.create(
            model=self._model,
            max_tokens=300,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text
