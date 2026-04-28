import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from celery_app.settings import worker_settings


class Base(DeclarativeBase):
    pass


class TransactionType(str, enum.Enum):
    income = "income"
    expense = "expense"


class GoalStatus(str, enum.Enum):
    active = "active"
    achieved = "achieved"
    abandoned = "abandoned"


class AIMode(str, enum.Enum):
    ollama = "ollama"
    api_key = "api_key"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), default=datetime.utcnow
    )


class FinancialWeek(Base):
    __tablename__ = "financial_weeks"
    __table_args__ = (UniqueConstraint("user_id", "week_start"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    week_end: Mapped[date] = mapped_column(Date, nullable=False)
    opening_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    closing_balance: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), default=datetime.utcnow)


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    week_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("financial_weeks.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    type: Mapped[TransactionType] = mapped_column(Enum(TransactionType), nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    recurrence_rule: Mapped[str | None] = mapped_column(String(50), nullable=True)
    transaction_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), default=datetime.utcnow)


class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    target_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    target_date: Mapped[date] = mapped_column(Date, nullable=False)
    current_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    status: Mapped[GoalStatus] = mapped_column(Enum(GoalStatus), default=GoalStatus.active)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), default=datetime.utcnow)


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
    api_key_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    ollama_url: Mapped[str] = mapped_column(String(255), default="http://localhost:11434")
    ollama_model: Mapped[str] = mapped_column(String(100), default="llama3.2")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class UserFinancialSettings(Base):
    __tablename__ = "user_financial_settings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True, nullable=False)
    initial_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    initial_balance_date: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


_engine = None


def _sync_url(url: str) -> str:
    return (
        url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
        .replace("postgresql+aiopg://", "postgresql+psycopg2://")
    )


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(_sync_url(worker_settings.DATABASE_URL), pool_pre_ping=True)
    return _engine


def get_session() -> Session:
    return Session(get_engine())
