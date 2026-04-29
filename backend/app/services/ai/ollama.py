import httpx

from .base import AI_TIMEOUT


class OllamaProvider:
    def __init__(self, url: str, model: str) -> None:
        self._url = url.rstrip("/")
        self._model = model

    async def generate(self, prompt: str, system: str) -> str:
        async with httpx.AsyncClient(timeout=AI_TIMEOUT) as client:
            resp = await client.post(
                f"{self._url}/api/generate",
                json={
                    "model": self._model,
                    "prompt": prompt,
                    "system": system,
                    "stream": False,
                },
            )
            resp.raise_for_status()
            return resp.json()["response"]
