import google.generativeai as genai


class GeminiProvider:
    def __init__(self, api_key: str, model: str) -> None:
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
