import asyncio
import logging
import os
import signal
import time
from datetime import datetime, timezone
from pathlib import Path

import aioboto3
import boto3
from aiokafka import AIOKafkaConsumer

logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_AUDIT_TOPIC = os.environ.get("KAFKA_AUDIT_TOPIC", "finflow.audit")
S3_AUDIT_BUCKET = os.environ.get("S3_AUDIT_BUCKET", "")
AWS_REGION = os.environ.get("AWS_REGION", "eu-west-1")

_BATCH_SIZE = 100
_FLUSH_INTERVAL = 300  # 5 minutes
_S3_MAX_ATTEMPTS = 3
_CW_NAMESPACE = "FinFlow/Audit"
_CW_METRIC_S3_FAILURE = "AuditS3WriteFailures"


def _emit_s3_failure_metric() -> None:
    """Push a single Count=1 data point when an audit batch falls back to local disk.

    Swallows any emission failure — must never raise from the consumer loop.
    """
    try:
        cw = boto3.client("cloudwatch", region_name=AWS_REGION)
        cw.put_metric_data(
            Namespace=_CW_NAMESPACE,
            MetricData=[{"MetricName": _CW_METRIC_S3_FAILURE, "Value": 1, "Unit": "Count"}],
        )
    except Exception as exc:
        logger.warning("Failed to emit audit S3-failure metric: %s", exc)


def _write_local(batch: list[bytes], now: datetime) -> None:
    content = b"\n".join(batch)
    path = Path("audit_archive") / now.strftime("%Y/%m/%d")
    path.mkdir(parents=True, exist_ok=True)
    filepath = path / f"{now.strftime('%H-%M-%S')}.jsonl"
    filepath.write_bytes(content)
    logger.info("Written %d events to %s (local)", len(batch), filepath)


async def _write_batch(batch: list[bytes]) -> None:
    now = datetime.now(timezone.utc)

    if not S3_AUDIT_BUCKET:
        _write_local(batch, now)
        return

    content = b"\n".join(batch)
    key = f"audit/{now.strftime('%Y/%m/%d/%H-%M-%S')}.jsonl"

    for attempt in range(_S3_MAX_ATTEMPTS):
        try:
            async with aioboto3.Session().client("s3", region_name=AWS_REGION) as s3:
                await s3.put_object(Bucket=S3_AUDIT_BUCKET, Key=key, Body=content)
            logger.info("Written %d events to s3://%s/%s", len(batch), S3_AUDIT_BUCKET, key)
            return
        except Exception as exc:
            logger.warning(
                "S3 audit write attempt %d/%d failed: %s", attempt + 1, _S3_MAX_ATTEMPTS, exc
            )
            if attempt < _S3_MAX_ATTEMPTS - 1:
                await asyncio.sleep(2**attempt)

    logger.error(
        "S3 audit write failed after %d attempts — falling back to local disk",
        _S3_MAX_ATTEMPTS,
    )
    _emit_s3_failure_metric()
    _write_local(batch, now)


async def run_consumer() -> None:
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()
    loop.add_signal_handler(signal.SIGTERM, stop_event.set)
    loop.add_signal_handler(signal.SIGINT, stop_event.set)

    consumer = AIOKafkaConsumer(
        KAFKA_AUDIT_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        group_id="finflow-audit-consumer",
        auto_offset_reset="earliest",
        enable_auto_commit=True,
    )
    await consumer.start()
    logger.info("Audit consumer started — topic=%s", KAFKA_AUDIT_TOPIC)

    batch: list[bytes] = []
    last_flush = time.monotonic()

    try:
        while not stop_event.is_set():
            records = await consumer.getmany(
                timeout_ms=1000,
                max_records=_BATCH_SIZE - len(batch),
            )
            for partition_records in records.values():
                for record in partition_records:
                    batch.append(record.value)

            now = time.monotonic()
            time_elapsed = now - last_flush >= _FLUSH_INTERVAL
            if len(batch) >= _BATCH_SIZE or (batch and time_elapsed):
                await _write_batch(batch)
                batch.clear()
                last_flush = time.monotonic()

    finally:
        if batch:
            logger.info("Flushing %d remaining events on shutdown", len(batch))
            await _write_batch(batch)
        await consumer.stop()
        logger.info("Audit consumer stopped")


if __name__ == "__main__":
    from logging_config import setup_logging
    setup_logging()
    asyncio.run(run_consumer())
