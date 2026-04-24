from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    DATABASE_URL: str

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


settings = Settings()
