from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.secrets import get_secret


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Frontend (CORS)
    FRONTEND_URL: str = "http://localhost:5173"

    # Database
    DATABASE_URL: str
    # Postgres is publicly reachable over the internet (Free-Tier trade-off — see
    # ARCHITECTURE_NOTES.md); this forces an encrypted-but-unverified TLS channel
    # (the realistic option without a private CA to distribute) so credentials and
    # data aren't sent in plaintext. Terraform sets it to true for the Lambda
    # deployment only — local/Docker/CI Postgres has no TLS configured.
    DATABASE_SSL_REQUIRE: bool = False
    DB_CONNECT_TIMEOUT: int = 5   # seconds to establish the TCP connection
    DB_STATEMENT_TIMEOUT: int = 15  # default timeout for every SQL command

    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080
    ENCRYPTION_KEY: str

    # AWS
    AWS_REGION: str = "eu-west-1"
    AWS_SNS_TOPIC_ARN: str = ""
    AWS_SQS_PROJECTIONS_URL: str = ""
    AWS_SQS_AI_ANALYSIS_URL: str = ""
    AWS_SQS_NOTIFICATIONS_URL: str = ""
    MAX_SNS_ATTEMPTS: int = 3

    # Kafka
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_AUDIT_TOPIC: str = "finflow.audit"

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # S3
    S3_AUDIT_BUCKET: str = ""

    # AI rate limiting
    AI_DAILY_RATE_LIMIT: int = 10


# DATABASE_URL/SECRET_KEY/ENCRYPTION_KEY are resolved through get_secret() so the
# Lambda deployment can fetch them from SSM at cold start instead of plaintext env
# vars (Terraform omits the env vars in production — see modules/compute). Locally
# and in CI the env vars are always set directly, so this is a no-op passthrough.
settings = Settings(
    DATABASE_URL=get_secret("DATABASE_URL", "database_url"),
    SECRET_KEY=get_secret("SECRET_KEY", "secret_key"),
    ENCRYPTION_KEY=get_secret("ENCRYPTION_KEY", "encryption_key"),
)
