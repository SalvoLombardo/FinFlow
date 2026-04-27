from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = ""
    AWS_REGION: str = "eu-west-1"
    AWS_SNS_TOPIC_ARN: str = ""
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_AUDIT_TOPIC: str = "finflow.audit"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"
    MAX_SNS_ATTEMPTS: int = 3


worker_settings = WorkerSettings()
