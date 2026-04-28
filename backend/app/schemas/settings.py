from datetime import date
from decimal import Decimal

from pydantic import BaseModel

from app.models.user_ai_settings import AIMode


class AISettingsRead(BaseModel):
    ai_enabled: bool
    ai_mode: AIMode
    ai_provider: str | None
    ai_model: str | None
    ollama_url: str
    ollama_model: str

    model_config = {"from_attributes": True}


class AISettingsUpdate(BaseModel):
    ai_enabled: bool | None = None
    ai_mode: AIMode | None = None
    ai_provider: str | None = None
    ai_model: str | None = None
    api_key: str | None = None   # plaintext — encrypted with Fernet before storage
    ollama_url: str | None = None
    ollama_model: str | None = None


class FinancialSettingsRead(BaseModel):
    initial_balance: float
    initial_balance_date: date

    model_config = {"from_attributes": True}


class FinancialSettingsUpdate(BaseModel):
    initial_balance: Decimal | None = None
    initial_balance_date: date | None = None
