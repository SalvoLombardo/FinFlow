from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


# ─────────────────────────────────────────────────────────────
# AT MODULE IMPORT (app startup)
# ─────────────────────────────────────────────────────────────

# 1. Base is defined — all SQLAlchemy models will inherit from this
class Base(DeclarativeBase):
    pass


# 2. Singleton variable is set to None — nothing is created yet.
#    We intentionally avoid reading settings here because environment
#    variables may not be loaded yet at import time.
_session_factory: async_sessionmaker | None = None


# ─────────────────────────────────────────────────────────────
# ON FIRST HTTP REQUEST — called once, then never again
# ─────────────────────────────────────────────────────────────

# 3. Called only on first request. Reads DATABASE_URL from settings
#    (safe now — env vars are fully loaded by the time a request arrives).
#    Creates the async engine with pool_pre_ping=True, which checks
#    that the connection is still alive before using it.
def _make_engine(url: str):
    return create_async_engine(url, echo=False, pool_pre_ping=True)


# 4. Builds the session factory using the engine created above.
#    expire_on_commit=False means SQLAlchemy won't expire object
#    attributes after commit — useful in async contexts where
#    lazy loading is not available.
def _build_session_factory() -> async_sessionmaker:
    from app.core.config import settings

    engine = _make_engine(settings.DATABASE_URL)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# 5. Called by get_db() on every request, but _build_session_factory()
#    is only triggered the first time (_session_factory is None).
#    From the second request onward, returns the existing singleton.
def get_session_factory() -> async_sessionmaker:
    global _session_factory
    if _session_factory is None:
        _session_factory = _build_session_factory()  # ← only called once
    return _session_factory


# ─────────────────────────────────────────────────────────────
# ON EVERY HTTP REQUEST — injected via Depends(get_db)
# ─────────────────────────────────────────────────────────────

# 6. FastAPI calls this for every route that declares:
#    db: AsyncSession = Depends(get_db)
#
#    Flow:
#      a) get_session_factory() returns the singleton
#      b) factory() opens a new session for this request
#      c) yield passes the session to the route
#      d) if the route completes successfully → commit
#      e) if the route raises an exception → rollback, then re-raise
#         (re-raise is critical: without it FastAPI would return 200
#          even if something went wrong)
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
