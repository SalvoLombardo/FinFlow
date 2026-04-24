from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.events.schemas import EventType, FinFlowEvent
from app.messaging.sns_publisher import SNSPublisher

FAKE_TOPIC_ARN = "arn:aws:sns:eu-west-1:123456789012:finflow-events"


def _make_event(event_type: EventType = EventType.BUDGET_UPDATED) -> FinFlowEvent:
    return FinFlowEvent(
        event_type=event_type,
        user_id="00000000-0000-0000-0000-000000000001",
        payload={"week_id": "00000000-0000-0000-0000-000000000002"},
    )


def _mock_session(client_mock: AsyncMock) -> MagicMock:
    """Build an aioboto3 session mock whose context-managed client returns client_mock."""
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=client_mock)
    ctx.__aexit__ = AsyncMock(return_value=False)
    session = MagicMock()
    session.client.return_value = ctx
    return session


@pytest.fixture
def publisher() -> SNSPublisher:
    return SNSPublisher()


# ── local mode ────────────────────────────────────────────────────────────────

async def test_local_mode_logs_instead_of_calling_aws(publisher, caplog):
    import logging

    with patch("app.messaging.sns_publisher.settings") as mock_cfg:
        mock_cfg.AWS_SNS_TOPIC_ARN = ""
        with caplog.at_level(logging.INFO, logger="app.messaging.sns_publisher"):
            await publisher.publish(_make_event())

    assert "SNS_LOCAL" in caplog.text


async def test_local_mode_does_not_create_boto_client(publisher):
    with patch("app.messaging.sns_publisher.settings") as mock_cfg, \
         patch("app.messaging.sns_publisher._session") as mock_session:
        mock_cfg.AWS_SNS_TOPIC_ARN = ""
        await publisher.publish(_make_event())

    mock_session.client.assert_not_called()


# ── cloud mode — happy path ───────────────────────────────────────────────────

async def test_cloud_mode_calls_sns_publish_once(publisher):
    client = AsyncMock()
    with patch("app.messaging.sns_publisher.settings") as mock_cfg, \
         patch("app.messaging.sns_publisher._session", _mock_session(client)):
        mock_cfg.AWS_SNS_TOPIC_ARN = FAKE_TOPIC_ARN
        mock_cfg.AWS_REGION = "eu-west-1"
        await publisher.publish(_make_event())

    client.publish.assert_awaited_once()


async def test_cloud_mode_message_attributes_contain_event_type(publisher):
    captured: dict = {}

    async def _fake_publish(**kwargs):
        captured.update(kwargs)

    client = AsyncMock()
    client.publish = _fake_publish

    with patch("app.messaging.sns_publisher.settings") as mock_cfg, \
         patch("app.messaging.sns_publisher._session", _mock_session(client)):
        mock_cfg.AWS_SNS_TOPIC_ARN = FAKE_TOPIC_ARN
        mock_cfg.AWS_REGION = "eu-west-1"
        await publisher.publish(_make_event(EventType.WEEK_CLOSED))

    attrs = captured.get("MessageAttributes", {})
    assert attrs.get("event_type", {}).get("StringValue") == "week.closed"


async def test_cloud_mode_uses_configured_topic_arn(publisher):
    captured: dict = {}

    async def _fake_publish(**kwargs):
        captured.update(kwargs)

    client = AsyncMock()
    client.publish = _fake_publish

    with patch("app.messaging.sns_publisher.settings") as mock_cfg, \
         patch("app.messaging.sns_publisher._session", _mock_session(client)):
        mock_cfg.AWS_SNS_TOPIC_ARN = FAKE_TOPIC_ARN
        mock_cfg.AWS_REGION = "eu-west-1"
        await publisher.publish(_make_event())

    assert captured.get("TopicArn") == FAKE_TOPIC_ARN


# ── cloud mode — retry logic ──────────────────────────────────────────────────

async def test_retries_on_transient_failure_and_succeeds(publisher):
    client = AsyncMock()
    client.publish = AsyncMock(side_effect=[Exception("timeout"), None])

    with patch("app.messaging.sns_publisher.settings") as mock_cfg, \
         patch("app.messaging.sns_publisher._session", _mock_session(client)), \
         patch("asyncio.sleep", new_callable=AsyncMock):
        mock_cfg.AWS_SNS_TOPIC_ARN = FAKE_TOPIC_ARN
        mock_cfg.AWS_REGION = "eu-west-1"
        await publisher.publish(_make_event())

    assert client.publish.await_count == 2


async def test_gives_up_after_max_attempts_without_raising(publisher):
    client = AsyncMock()
    client.publish = AsyncMock(side_effect=Exception("SNS unavailable"))

    with patch("app.messaging.sns_publisher.settings") as mock_cfg, \
         patch("app.messaging.sns_publisher._session", _mock_session(client)), \
         patch("asyncio.sleep", new_callable=AsyncMock):
        mock_cfg.AWS_SNS_TOPIC_ARN = FAKE_TOPIC_ARN
        mock_cfg.AWS_REGION = "eu-west-1"
        await publisher.publish(_make_event())  # must not raise

    assert client.publish.await_count == 3


async def test_error_does_not_propagate_to_caller(publisher):
    client = AsyncMock()
    client.publish = AsyncMock(side_effect=Exception("hard failure"))

    with patch("app.messaging.sns_publisher.settings") as mock_cfg, \
         patch("app.messaging.sns_publisher._session", _mock_session(client)), \
         patch("asyncio.sleep", new_callable=AsyncMock):
        mock_cfg.AWS_SNS_TOPIC_ARN = FAKE_TOPIC_ARN
        mock_cfg.AWS_REGION = "eu-west-1"
        try:
            await publisher.publish(_make_event())
        except Exception:
            pytest.fail("publish() must not propagate exceptions to the caller")
