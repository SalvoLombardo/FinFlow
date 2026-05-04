try:
    import google.generativeai as genai
except ImportError:
    genai = None  # type: ignore[assignment]


class GeminiProvider:
    def __init__(self, api_key: str, model: str) -> None:
        if genai is None:
            raise ImportError("google-generativeai package not available in this environment")
        genai.configure(api_key=api_key)
        self._model_name = model

    async def generate(self, prompt: str, system: str) -> str:
        # GenerativeModel is created per-call so system_instruction is always applied.
        model = genai.GenerativeModel(
            model_name=self._model_name,
            system_instruction=system,
        )
        resp = await model.generate_content_async(prompt)
        return resp.text
