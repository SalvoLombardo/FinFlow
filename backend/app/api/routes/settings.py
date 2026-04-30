from datetime import date

from cryptography.fernet import Fernet
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.models.user_ai_settings import UserAISettings
from app.models.user_financial_settings import UserFinancialSettings
from app.schemas.settings import (
    AISettingsRead,
    AISettingsUpdate,
    FinancialSettingsRead,
    FinancialSettingsUpdate,
)
from app.services.ai.service import AIService

router = APIRouter()


# ---------------------------------------------------------------------------
# AI settings
# ---------------------------------------------------------------------------

@router.get("/ai", response_model=AISettingsRead)
async def get_ai_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserAISettings).where(UserAISettings.user_id == current_user.id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        row = UserAISettings(user_id=current_user.id)
        db.add(row)
        await db.flush()
    return row


@router.put("/ai", response_model=AISettingsRead)
async def update_ai_settings(
    body: AISettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserAISettings).where(UserAISettings.user_id == current_user.id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        row = UserAISettings(user_id=current_user.id)
        db.add(row)

    for field in ("ai_enabled", "ai_mode", "ai_provider", "ai_model", "ollama_url", "ollama_model"):
        val = getattr(body, field)
        if val is not None:
            setattr(row, field, val)

    if body.api_key and body.api_key.strip() and settings.ENCRYPTION_KEY:
        f = Fernet(settings.ENCRYPTION_KEY.encode())
        row.api_key_enc = f.encrypt(body.api_key.encode()).decode()

    await db.flush()
    return row


@router.post("/ai/test", response_model=dict)
async def test_ai_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Call the configured AI provider with a fixed test prompt. Returns the raw response."""
    result = await db.execute(
        select(UserAISettings).where(UserAISettings.user_id == current_user.id)
    )
    row = result.scalar_one_or_none()
    if row is None or not row.ai_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="AI is not enabled. Enable it in Settings first.",
        )
    try:
        ai = AIService(row)
        response = await ai.generate_savings_tip(
            avg_weekly_income=500.0,
            avg_weekly_expense=400.0,
            top_categories=[("Spesa", 150.0), ("Trasporti", 80.0)],
            weeks_analyzed=4,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI provider error: {exc}",
        )
    return {"response": response}


# ---------------------------------------------------------------------------
# Financial settings (initial balance)
# ---------------------------------------------------------------------------

@router.get("/financial", response_model=FinancialSettingsRead)
async def get_financial_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserFinancialSettings).where(UserFinancialSettings.user_id == current_user.id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        row = UserFinancialSettings(user_id=current_user.id, initial_balance_date=date.today())
        db.add(row)
        await db.flush()
    return row


@router.put("/financial", response_model=FinancialSettingsRead)
async def update_financial_settings(
    body: FinancialSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserFinancialSettings).where(UserFinancialSettings.user_id == current_user.id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        row = UserFinancialSettings(user_id=current_user.id, initial_balance_date=date.today())
        db.add(row)

    if body.initial_balance is not None:
        row.initial_balance = body.initial_balance
    if body.initial_balance_date is not None:
        row.initial_balance_date = body.initial_balance_date

    await db.flush()
    return row
