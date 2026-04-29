from cryptography.fernet import Fernet

from app.core.config import settings
from app.models.user_ai_settings import AIMode, UserAISettings

from .anthropic_provider import AnthropicProvider
from .base import SYSTEM_PROMPT, AIProvider
from .gemini import GeminiProvider
from .ollama import OllamaProvider
from .openai_provider import OpenAIProvider

_DEFAULT_MODELS: dict[str, str] = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-haiku-4-5-20251001",
    "gemini": "gemini-1.5-flash",
}


class AIService:
    def __init__(self, ai_settings: UserAISettings) -> None:
        self._settings = ai_settings

    # ------------------------------------------------------------------
    # Provider factory
    # ------------------------------------------------------------------

    def _provider(self) -> AIProvider:
        s = self._settings
        if s.ai_mode == AIMode.ollama:
            return OllamaProvider(url=s.ollama_url, model=s.ollama_model)

        api_key = self._decrypt_key(s.api_key_enc)
        provider_name = s.ai_provider or ""
        model = s.ai_model or _DEFAULT_MODELS.get(provider_name, "gpt-4o-mini")

        if provider_name == "openai":
            return OpenAIProvider(api_key=api_key, model=model)
        if provider_name == "anthropic":
            return AnthropicProvider(api_key=api_key, model=model)
        if provider_name == "gemini":
            return GeminiProvider(api_key=api_key, model=model)
        raise ValueError(f"Unknown AI provider: {provider_name!r}")

    @staticmethod
    def _decrypt_key(enc: str | None) -> str:
        if not enc:
            raise ValueError("No API key stored. Configure it in Settings.")
        if not settings.ENCRYPTION_KEY:
            raise ValueError("Server ENCRYPTION_KEY not configured.")
        return Fernet(settings.ENCRYPTION_KEY.encode()).decrypt(enc.encode()).decode()

    # ------------------------------------------------------------------
    # Public generation methods
    # ------------------------------------------------------------------

    async def generate_weekly_insight(
        self,
        week_label: str,
        opening_balance: float,
        closing_balance: float,
        total_income: float,
        total_expense: float,
        top_categories: list[tuple[str, float]],
    ) -> str:
        cats = ", ".join(f"{c} (€{a:.0f})" for c, a in top_categories[:3]) or "nessuna"
        prompt = (
            f"Settimana {week_label}:\n"
            f"- Saldo apertura: €{opening_balance:.2f}\n"
            f"- Entrate: €{total_income:.2f}   Uscite: €{total_expense:.2f}\n"
            f"- Saldo chiusura: €{closing_balance:.2f}\n"
            f"- Categorie principali: {cats}\n\n"
            "Dimmi qualcosa di utile su questa settimana."
        )
        return await self._provider().generate(prompt, SYSTEM_PROMPT)

    async def generate_savings_tip(
        self,
        avg_weekly_income: float,
        avg_weekly_expense: float,
        top_categories: list[tuple[str, float]],
        weeks_analyzed: int,
    ) -> str:
        cats = ", ".join(f"{c} (€{a:.0f})" for c, a in top_categories[:5]) or "nessuna"
        net = avg_weekly_income - avg_weekly_expense
        prompt = (
            f"Ultime {weeks_analyzed} settimane analizzate:\n"
            f"- Media entrate settimanali: €{avg_weekly_income:.2f}\n"
            f"- Media uscite settimanali: €{avg_weekly_expense:.2f}\n"
            f"- Risparmio netto medio: €{net:.2f}\n"
            f"- Principali categorie di spesa: {cats}\n\n"
            "Dammi un consiglio pratico per risparmiare di più."
        )
        return await self._provider().generate(prompt, SYSTEM_PROMPT)

    async def generate_goal_advice(
        self,
        goal_name: str,
        target_amount: float,
        current_amount: float,
        target_date: str,
        avg_weekly_savings: float,
    ) -> str:
        remaining = target_amount - current_amount
        pct = (current_amount / target_amount * 100) if target_amount else 0
        prompt = (
            f"Obiettivo: {goal_name}\n"
            f"- Target: €{target_amount:.2f}   Raggiunto: €{current_amount:.2f} ({pct:.0f}%)\n"
            f"- Mancano: €{remaining:.2f}   Scadenza: {target_date}\n"
            f"- Risparmio medio settimanale attuale: €{avg_weekly_savings:.2f}\n\n"
            "Come posso raggiungere questo obiettivo?"
        )
        return await self._provider().generate(prompt, SYSTEM_PROMPT)
