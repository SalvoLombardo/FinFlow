import logging
import os

import boto3
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

logger = logging.getLogger()
logger.setLevel(logging.INFO)

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


# NullPool: avoids stale connections across Lambda invocations with different event loops.
engine = create_async_engine(get_secret("DATABASE_URL", "database_url"), poolclass=NullPool)
Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class SQSEvent(BaseModel):
    """Envelope common to all three SQS consumer handlers."""
    event_type: str
    user_id: str
    payload: dict
