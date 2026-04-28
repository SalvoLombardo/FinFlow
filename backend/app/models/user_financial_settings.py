import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Numeric, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserFinancialSettings(Base):
    __tablename__ = "user_financial_settings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, unique=True)
    initial_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    initial_balance_date: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), default=datetime.utcnow
    )
