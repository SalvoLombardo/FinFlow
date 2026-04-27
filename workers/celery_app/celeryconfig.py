from celery_app.settings import worker_settings

broker_url = worker_settings.CELERY_BROKER_URL
result_backend = worker_settings.CELERY_RESULT_BACKEND
task_serializer = "json"
result_serializer = "json"
accept_content = ["json"]
timezone = "UTC"
enable_utc = True
redbeat_redis_url = worker_settings.CELERY_BROKER_URL
