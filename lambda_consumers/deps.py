import logging
import os

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# NullPool: avoids stale connections across Lambda invocations with different event loops.
engine = create_async_engine(os.environ["DATABASE_URL"], poolclass=NullPool)
Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class SQSEvent(BaseModel):
    """Envelope common to all three SQS consumer handlers."""
    event_type: str
    user_id: str
    payload: dict
