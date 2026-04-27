from cryptography.fernet import Fernet
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.models.user_ai_settings import UserAISettings
from app.schemas.settings import AISettingsRead, AISettingsUpdate

router = APIRouter()


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
