import asyncio
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from kafka_audit.producer import AuditEvent, KafkaAuditProducer, _emit_drop_metric


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _event(**kwargs) -> AuditEvent:
    defaults = dict(
        user_id="user-1",
        action="create",
        entity_type="transaction",
        entity_id="txn-1",
        after_state={"amount": 100},
    )
    return AuditEvent(**(defaults | kwargs))


def _mock_kafka_producer(send_side_effect=None) -> AsyncMock:
    p = AsyncMock()
    if send_side_effect is not None:
        p.send_and_wait.side_effect = send_side_effect
    return p


# ---------------------------------------------------------------------------
# KafkaAuditProducer.send — success paths
# ---------------------------------------------------------------------------


async def test_send_success_on_first_attempt():
    mock_producer = _mock_kafka_producer()
    with patch("kafka_audit.producer.AIOKafkaProducer", return_value=mock_producer):
        await KafkaAuditProducer().send(_event())

    mock_producer.start.assert_called_once()
    mock_producer.send_and_wait.assert_called_once()
    mock_producer.stop.assert_called_once()


async def test_send_retries_once_then_succeeds():
    """First attempt raises; second succeeds — stop() must still be called each time."""
    mock_producer = _mock_kafka_producer(send_side_effect=[Exception("connect timeout"), None])
    with (
        patch("kafka_audit.producer.AIOKafkaProducer", return_value=mock_producer),
        patch("kafka_audit.producer.asyncio.sleep"),
    ):
        await KafkaAuditProducer().send(_event())

    assert mock_producer.send_and_wait.call_count == 2
    assert mock_producer.stop.call_count == 2


async def test_send_stops_producer_even_on_send_failure():
    """stop() must be called in the finally block even when send_and_wait raises."""
    mock_producer = _mock_kafka_producer(send_side_effect=Exception("nack"))
    with (
        patch("kafka_audit.producer.AIOKafkaProducer", return_value=mock_producer),
        patch("kafka_audit.producer.asyncio.sleep"),
        patch("kafka_audit.producer._emit_drop_metric"),
    ):
        await KafkaAuditProducer().send(_event())

    # 3 attempts → 3 stop() calls
    assert mock_producer.stop.call_count == 3


# ---------------------------------------------------------------------------
# KafkaAuditProducer.send — all-attempts-exhausted path
# ---------------------------------------------------------------------------


async def test_send_all_attempts_fail_emits_cloudwatch_metric():
    mock_producer = _mock_kafka_producer(send_side_effect=Exception("kafka down"))
    mock_cw = MagicMock()
    with (
        patch("kafka_audit.producer.AIOKafkaProducer", return_value=mock_producer),
        patch("kafka_audit.producer.asyncio.sleep"),
        patch("kafka_audit.producer.boto3.client", return_value=mock_cw),
    ):
        await KafkaAuditProducer().send(_event(action="delete"))

    assert mock_producer.send_and_wait.call_count == 3
    mock_cw.put_metric_data.assert_called_once()
    call_kwargs = mock_cw.put_metric_data.call_args.kwargs
    assert call_kwargs["Namespace"] == "FinFlow/Audit"
    assert call_kwargs["MetricData"][0]["MetricName"] == "DroppedAuditEvents"
    assert call_kwargs["MetricData"][0]["Dimensions"][0]["Value"] == "delete"


async def test_send_all_attempts_fail_does_not_raise():
    """send() is fire-and-forget — it must never propagate an exception to the caller."""
    mock_producer = _mock_kafka_producer(send_side_effect=Exception("kafka down"))
    with (
        patch("kafka_audit.producer.AIOKafkaProducer", return_value=mock_producer),
        patch("kafka_audit.producer.asyncio.sleep"),
        patch("kafka_audit.producer._emit_drop_metric"),
    ):
        # Should complete without raising
        await KafkaAuditProducer().send(_event())


# ---------------------------------------------------------------------------
# _emit_drop_metric — resilience
# ---------------------------------------------------------------------------


def test_emit_drop_metric_does_not_raise_on_cloudwatch_failure():
    """If put_metric_data itself fails, _emit_drop_metric must swallow the exception."""
    mock_cw = MagicMock()
    mock_cw.put_metric_data.side_effect = Exception("cw unavailable")
    with patch("kafka_audit.producer.boto3.client", return_value=mock_cw):
        _emit_drop_metric("create")  # must not raise


def test_emit_drop_metric_calls_put_metric_data_with_correct_args():
    mock_cw = MagicMock()
    with patch("kafka_audit.producer.boto3.client", return_value=mock_cw):
        _emit_drop_metric("budget.updated")

    mock_cw.put_metric_data.assert_called_once()
    md = mock_cw.put_metric_data.call_args.kwargs["MetricData"][0]
    assert md["MetricName"] == "DroppedAuditEvents"
    assert md["Value"] == 1
    assert md["Unit"] == "Count"
    assert md["Dimensions"][0] == {"Name": "Action", "Value": "budget.updated"}


# ---------------------------------------------------------------------------
# _write_batch — S3 path
# ---------------------------------------------------------------------------


async def test_write_batch_s3_puts_newline_joined_content():
    batch = [b'{"a":1}', b'{"a":2}']
    mock_s3 = AsyncMock()
    mock_session = MagicMock()
    mock_session.client.return_value.__aenter__ = AsyncMock(return_value=mock_s3)
    mock_session.client.return_value.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("kafka_audit.consumer.S3_AUDIT_BUCKET", "my-bucket"),
        patch("kafka_audit.consumer.aioboto3.Session", return_value=mock_session),
    ):
        from kafka_audit.consumer import _write_batch
        await _write_batch(batch)

    mock_s3.put_object.assert_called_once()
    kwargs = mock_s3.put_object.call_args.kwargs
    assert kwargs["Bucket"] == "my-bucket"
    assert kwargs["Body"] == b'{"a":1}\n{"a":2}'
    assert kwargs["Key"].startswith("audit/")
    assert kwargs["Key"].endswith(".jsonl")


async def test_write_batch_s3_retries_then_succeeds():
    """First attempt fails, second succeeds — no fallback, no metric."""
    mock_s3 = AsyncMock()
    mock_s3.put_object.side_effect = [Exception("transient"), None]
    mock_session = MagicMock()
    mock_session.client.return_value.__aenter__ = AsyncMock(return_value=mock_s3)
    mock_session.client.return_value.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("kafka_audit.consumer.S3_AUDIT_BUCKET", "my-bucket"),
        patch("kafka_audit.consumer.aioboto3.Session", return_value=mock_session),
        patch("kafka_audit.consumer.asyncio.sleep", new=AsyncMock()),
        patch("kafka_audit.consumer._emit_s3_failure_metric") as mock_metric,
        patch("kafka_audit.consumer._write_local") as mock_local,
    ):
        from kafka_audit.consumer import _write_batch
        await _write_batch([b'{"a":1}'])

    assert mock_s3.put_object.call_count == 2
    mock_metric.assert_not_called()
    mock_local.assert_not_called()


async def test_write_batch_s3_failure_falls_back_to_local_and_emits_metric():
    """All S3 attempts fail — batch is written locally and a CloudWatch metric is emitted."""
    mock_s3 = AsyncMock()
    mock_s3.put_object.side_effect = Exception("S3 unavailable")
    mock_session = MagicMock()
    mock_session.client.return_value.__aenter__ = AsyncMock(return_value=mock_s3)
    mock_session.client.return_value.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("kafka_audit.consumer.S3_AUDIT_BUCKET", "my-bucket"),
        patch("kafka_audit.consumer.aioboto3.Session", return_value=mock_session),
        patch("kafka_audit.consumer.asyncio.sleep", new=AsyncMock()),
        patch("kafka_audit.consumer._emit_s3_failure_metric") as mock_metric,
        patch("kafka_audit.consumer._write_local") as mock_local,
    ):
        from kafka_audit.consumer import _write_batch
        await _write_batch([b'{"a":1}'])

    assert mock_s3.put_object.call_count == 3
    mock_metric.assert_called_once()
    mock_local.assert_called_once()


def test_emit_s3_failure_metric_calls_put_metric_data_with_correct_args():
    mock_cw = MagicMock()
    with patch("kafka_audit.consumer.boto3.client", return_value=mock_cw):
        from kafka_audit.consumer import _emit_s3_failure_metric
        _emit_s3_failure_metric()

    mock_cw.put_metric_data.assert_called_once()
    kwargs = mock_cw.put_metric_data.call_args.kwargs
    assert kwargs["Namespace"] == "FinFlow/Audit"
    assert kwargs["MetricData"][0]["MetricName"] == "AuditS3WriteFailures"


def test_emit_s3_failure_metric_does_not_raise_on_cloudwatch_failure():
    mock_cw = MagicMock()
    mock_cw.put_metric_data.side_effect = Exception("cw unavailable")
    with patch("kafka_audit.consumer.boto3.client", return_value=mock_cw):
        from kafka_audit.consumer import _emit_s3_failure_metric
        _emit_s3_failure_metric()  # must not raise


# ---------------------------------------------------------------------------
# _write_batch — local fallback path
# ---------------------------------------------------------------------------


async def test_write_batch_local_writes_file(tmp_path):
    batch = [b'{"x":1}', b'{"x":2}']

    with (
        patch("kafka_audit.consumer.S3_AUDIT_BUCKET", ""),
        patch("kafka_audit.consumer.Path", wraps=lambda p: tmp_path / p),
    ):
        from kafka_audit.consumer import _write_batch
        await _write_batch(batch)

    # At least one .jsonl file was written under tmp_path
    written = list(tmp_path.rglob("*.jsonl"))
    assert written, "Expected at least one .jsonl file written locally"
    content = written[0].read_bytes()
    assert b'{"x":1}' in content
    assert b'{"x":2}' in content
