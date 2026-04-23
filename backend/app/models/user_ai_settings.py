import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AIMode(str, enum.Enum):
    ollama = "ollama"
    api_key = "api_key"


class UserAISettings(Base):
    __tablename__ = "user_ai_settings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False
    )
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_mode: Mapped[AIMode] = mapped_column(Enum(AIMode), default=AIMode.api_key)
    ai_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ai_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    api_key_enc: Mapped[str | None] = mapped_column(Text, nullable=True)  # encrypted with Fernet
    ollama_url: Mapped[str] = mapped_column(String(255), default="http://localhost:11434")
    ollama_model: Mapped[str] = mapped_column(String(100), default="llama3.2")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
