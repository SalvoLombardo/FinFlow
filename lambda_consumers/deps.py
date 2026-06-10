import json
import logging
import os
import ssl
from contextvars import ContextVar

import boto3
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

# ---------------------------------------------------------------------------
# Structured JSON logging + per-message trace ID
# ---------------------------------------------------------------------------

_trace_id: ContextVar[str] = ContextVar("trace_id", default="-")


def get_trace_id() -> str:
    return _trace_id.get()


def set_trace_id(tid: str) -> None:
    _trace_id.set(tid or "-")


class _JsonFormatter(logging.Formatter):
    """Emit each log record as a single JSON line for CloudWatch Logs Insights."""

    def format(self, record: logging.LogRecord) -> str:
        data: dict = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "trace_id": _trace_id.get(),
            "msg": record.getMessage(),
        }
        if record.exc_info:
            data["exc"] = self.formatException(record.exc_info)
        return json.dumps(data, ensure_ascii=False)


def _setup_logging() -> None:
    formatter = _JsonFormatter()
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)


_setup_logging()

logger = logging.getLogger(__name__)

_ssm_client = None
_secret_cache: dict[str, str] = {}


def get_secret(env_var: str, ssm_name: str) -> str:
    """Resolve a runtime secret.

    Prefers a plain env var (Docker/local/CI/tests always set these directly).
    Falls back to an SSM SecureString — fetched once per cold start and cached
    for the lifetime of the warm Lambda — for the production deployment, where
    Terraform intentionally omits the plaintext env var to avoid double exposure
    (Lambda console + CloudWatch + Terraform state).
    """
    value = os.environ.get(env_var)
    if value:
        return value

    if ssm_name not in _secret_cache:
        prefix = os.environ.get("SSM_PARAMETER_PREFIX")
        if not prefix:
            raise RuntimeError(
                f"{env_var} is not set and SSM_PARAMETER_PREFIX is missing — "
                f"cannot resolve secret '{ssm_name}'"
            )
        global _ssm_client
        if _ssm_client is None:
            _ssm_client = boto3.client("ssm", region_name=os.environ.get("AWS_REGION", "eu-west-1"))
        response = _ssm_client.get_parameter(Name=f"{prefix}/{ssm_name}", WithDecryption=True)
        _secret_cache[ssm_name] = response["Parameter"]["Value"]

    return _secret_cache[ssm_name]


# Postgres is publicly reachable with no private CA to issue/verify a trusted
# certificate against — DATABASE_SSL_REQUIRE (set by Terraform for this Lambda
# deployment only) asks asyncpg to encrypt the channel without verifying the
# server's (self-signed) identity, stopping passive sniffing of credentials/data
# in transit. Local/Docker/CI Postgres has no TLS configured, so this stays off
# there. See PRODUCTION_READINESS.md "public Postgres" finding.
def _ssl_connect_args() -> dict:
    if os.environ.get("DATABASE_SSL_REQUIRE", "").lower() not in ("1", "true", "yes"):
        return {}
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return {"ssl": context}


_DB_CONNECT_TIMEOUT = int(os.environ.get("DB_CONNECT_TIMEOUT", "5"))
_DB_STATEMENT_TIMEOUT = int(os.environ.get("DB_STATEMENT_TIMEOUT", "15"))

# NullPool: avoids stale connections across Lambda invocations with different event loops.
engine = create_async_engine(
    get_secret("DATABASE_URL", "database_url"),
    poolclass=NullPool,
    connect_args={**_ssl_connect_args(), "connect_timeout": _DB_CONNECT_TIMEOUT, "command_timeout": _DB_STATEMENT_TIMEOUT},
)
Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class SQSEvent(BaseModel):
    """Envelope common to all three SQS consumer handlers."""
    event_id: str = ""   # populated from FinFlowEvent.event_id; used as trace_id in logs
    event_type: str
    user_id: str
    payload: dict
