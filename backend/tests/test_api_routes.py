import uuid
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from app.api.deps import get_current_user
from app.core.database import get_db
from app.main import app
from app.models.goal import Goal, GoalStatus
from app.models.transaction import Transaction, TransactionType
from app.models.week import FinancialWeek
from tests.conftest import make_mock_result


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def test_register_new_user(mock_db):
    mock_db.execute.return_value = make_mock_result(scalar_one=None)

    from fastapi.testclient import TestClient

    async def override_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as c:
        r = c.post("/api/v1/auth/register", json={"email": "new@example.com", "password": "secret123"})
    app.dependency_overrides.clear()

    assert r.status_code == 201
    data = r.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_register_duplicate_email_returns_400(mock_db, test_user):
    mock_db.execute.return_value = make_mock_result(scalar_one=test_user)

    from fastapi.testclient import TestClient

    async def override_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as c:
        r = c.post("/api/v1/auth/register", json={"email": "user@example.com", "password": "secret"})
    app.dependency_overrides.clear()

    assert r.status_code == 400


def test_login_valid_credentials(mock_db, test_user):
    from app.services.auth import hash_password

    test_user.hashed_password = hash_password("password123")
    mock_db.execute.return_value = make_mock_result(scalar_one=test_user)

    from fastapi.testclient import TestClient

    async def override_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as c:
        r = c.post("/api/v1/auth/login", json={"email": test_user.email, "password": "password123"})
    app.dependency_overrides.clear()

    assert r.status_code == 200
    assert "access_token" in r.json()


def test_login_wrong_password_returns_401(mock_db, test_user):
    from app.services.auth import hash_password

    test_user.hashed_password = hash_password("correctpassword")
    mock_db.execute.return_value = make_mock_result(scalar_one=test_user)

    from fastapi.testclient import TestClient

    async def override_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as c:
        r = c.post("/api/v1/auth/login", json={"email": test_user.email, "password": "wrongpassword"})
    app.dependency_overrides.clear()

    assert r.status_code == 401


def test_me_returns_current_user(client, test_user):
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 200
    assert r.json()["email"] == test_user.email


# ---------------------------------------------------------------------------
# Weeks
# ---------------------------------------------------------------------------

def test_list_weeks_empty(client, mock_db):
    with patch("app.api.routes.weeks.calculate_projection", new_callable=AsyncMock) as mock_proj:
        mock_proj.return_value = []
        r = client.get("/api/v1/weeks")
    assert r.status_code == 200
    assert r.json() == []


def test_list_weeks_returns_data(client, mock_db, test_user):
    from app.services.projection import WeekSummaryData
    from datetime import timedelta

    monday = date(2024, 1, 1)
    fake = [
        WeekSummaryData(
            week_id=uuid.uuid4(),
            week_start=monday,
            week_end=monday + timedelta(days=6),
            opening_balance=Decimal("1000"),
            closing_balance=Decimal("1200"),
            total_income=Decimal("200"),
            total_expense=Decimal("0"),
            is_projected=False,
        )
    ]
    with patch("app.api.routes.weeks.calculate_projection", new_callable=AsyncMock) as mock_proj:
        mock_proj.return_value = fake
        r = client.get("/api/v1/weeks")
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["total_income"] == 200.0


def test_get_week_not_found(client, mock_db):
    mock_db.execute.return_value = make_mock_result(scalar_one=None)
    r = client.get(f"/api/v1/weeks/{uuid.uuid4()}")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------

def test_list_transactions_empty(client, mock_db):
    mock_db.execute.return_value = make_mock_result(scalars_list=[])
    r = client.get("/api/v1/transactions")
    assert r.status_code == 200
    assert r.json() == []


def test_create_transaction(client, mock_db):
    week = FinancialWeek(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        week_start=date(2024, 1, 1),
        week_end=date(2024, 1, 7),
        opening_balance=Decimal("0"),
        created_at=datetime(2024, 1, 1),
    )
    mock_db.execute.return_value = make_mock_result(scalar_one=week)

    with patch("app.api.routes.transactions.get_or_create_week", new_callable=AsyncMock, return_value=week), \
         patch("app.api.routes.transactions.sns_publisher.publish", new_callable=AsyncMock), \
         patch("app.api.routes.transactions.audit_producer.send", new_callable=AsyncMock):
        r = client.post("/api/v1/transactions", json={
            "name": "Coffee",
            "amount": "5.50",
            "type": "expense",
            "transaction_date": "2024-01-03",
        })
    assert r.status_code == 201
    mock_db.add.assert_called_once()


def test_delete_transaction_not_found(client, mock_db):
    mock_db.execute.return_value = make_mock_result(scalar_one=None)
    r = client.delete(f"/api/v1/transactions/{uuid.uuid4()}")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Goals
# ---------------------------------------------------------------------------

def test_list_goals_empty(client, mock_db):
    with patch("app.api.routes.goals.calculate_projection", new_callable=AsyncMock) as mock_proj:
        mock_proj.return_value = []
        mock_db.execute.return_value = make_mock_result(scalars_list=[])
        r = client.get("/api/v1/goals")
    assert r.status_code == 200
    assert r.json() == []


def test_create_goal(client, mock_db):
    from app.services.projection import WeekSummaryData
    from datetime import timedelta

    monday = date(2024, 1, 1)
    fake_summary = WeekSummaryData(
        week_id=None, week_start=monday, week_end=monday + timedelta(days=6),
        opening_balance=Decimal("0"), closing_balance=Decimal("1000"),
        total_income=Decimal("0"), total_expense=Decimal("0"), is_projected=False,
    )
    with patch("app.api.routes.goals.calculate_projection", new_callable=AsyncMock) as mock_proj:
        mock_proj.return_value = [fake_summary]
        r = client.post("/api/v1/goals", json={
            "name": "Emergency Fund",
            "target_amount": "5000.00",
            "target_date": "2024-12-31",
            "goal_type": "savings",
        })
    assert r.status_code == 201
    mock_db.add.assert_called_once()


def test_update_goal_not_found(client, mock_db):
    mock_db.execute.return_value = make_mock_result(scalar_one=None)
    r = client.put(f"/api/v1/goals/{uuid.uuid4()}", json={"name": "New name"})
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

def test_dashboard_summary(client, mock_db, test_user):
    from app.services.projection import WeekSummaryData
    from datetime import timedelta

    start = date(2024, 1, 1)
    fake_projection = [
        WeekSummaryData(
            week_id=None,
            week_start=start + timedelta(weeks=i),
            week_end=start + timedelta(weeks=i, days=6),
            opening_balance=Decimal("100"),
            closing_balance=Decimal("100"),
            total_income=Decimal("0"),
            total_expense=Decimal("0"),
            is_projected=(i > 0),
        )
        for i in range(8)
    ]

    with patch("app.api.routes.dashboard.calculate_projection", new_callable=AsyncMock) as mock_proj:
        mock_proj.return_value = fake_projection
        mock_db.execute.return_value = make_mock_result(scalars_list=[])
        r = client.get("/api/v1/dashboard/summary")

    assert r.status_code == 200
    data = r.json()
    assert "current_balance" in data
    assert len(data["projection"]) == 8
    assert data["goals"] == []
