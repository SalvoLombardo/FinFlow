import os

import boto3

_ssm_client = None
_secret_cache: dict[str, str] = {}


def get_secret(env_var: str, ssm_name: str) -> str:
    """Resolve a runtime secret.

    Prefers a plain env var (Docker Compose injects `.env` into the container,
    and tests/CI set these directly). Falls back to an SSM SecureString —
    fetched once per cold start and cached for the lifetime of the warm Lambda
    — for the production deployment, where Terraform intentionally omits the
    plaintext env var to avoid double exposure (Lambda console + CloudWatch +
    Terraform state).
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
