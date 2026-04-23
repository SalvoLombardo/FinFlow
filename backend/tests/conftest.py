import os

# Must be set before any app.* import so pydantic-settings can read them
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-only!!")
os.environ.setdefault("ENCRYPTION_KEY", "test-encryption-key-32-characters!!")

import uuid  # noqa: E402
from datetime import datetime  # noqa: E402
from unittest.mock import AsyncMock, MagicMock  # noqa: E402

import pytest  # noqa: E402

from app.api.deps import get_current_user  # noqa: E402
from app.core.database import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.user import User  # noqa: E402


def make_mock_result(
    scalars_list=None,
    scalar_one=None,
    rows=None,
):
    """Build a mock that mirrors SQLAlchemy AsyncResult patterns."""
    result = MagicMock()
    result.scalars.return_value.all.return_value = scalars_list if scalars_list is not None else []
    result.scalar_one_or_none.return_value = scalar_one
    result.all.return_value = rows if rows is not None else []
    return result


@pytest.fixture
def user_id():
    return uuid.uuid4()


@pytest.fixture
def test_user():
    return User(
        id=uuid.uuid4(),
        email="user@example.com",
        hashed_password="hashed",
        created_at=datetime(2024, 1, 1),
        updated_at=datetime(2024, 1, 1),
    )


def _simulate_add(obj):
    """Apply Python-level column defaults, simulating what SQLAlchemy does at flush time."""
    from sqlalchemy import inspect as sa_inspect

    try:
        state = sa_inspect(obj)          # InstanceState for this ORM object
        for col_attr in state.mapper.column_attrs:
            col = col_attr.columns[0]
            if col.default is None:
                continue
            if getattr(obj, col_attr.key, None) is not None:
                continue
            arg = col.default.arg
            try:
                # SQLAlchemy 2.x wraps zero-arg callables as `lambda ctx: original()`
                # so we pass None as the execution context
                val = arg(None) if callable(arg) else arg
                setattr(obj, col_attr.key, val)
            except Exception:
                pass
    except Exception:
        pass


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.flush = AsyncMock()
    db.delete = AsyncMock()
    db.add = MagicMock(side_effect=_simulate_add)
    return db


@pytest.fixture
def client(mock_db, test_user):
    from fastapi.testclient import TestClient

    async def override_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: test_user

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()
