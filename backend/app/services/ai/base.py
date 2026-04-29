from typing import Protocol, runtime_checkable

SYSTEM_PROMPT = (
    "Sei un assistente finanziario personale amichevole e pratico. "
    "Dai consigli concreti basati sui dati reali. Rispondi in italiano. "
    "Max 3-4 frasi. Parla come un amico esperto, non come un chatbot."
)

AI_TIMEOUT = 30.0  # seconds


@runtime_checkable
class AIProvider(Protocol):
    async def generate(self, prompt: str, system: str) -> str: ...
