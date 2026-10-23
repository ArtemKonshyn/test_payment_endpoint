import os
from datetime import timedelta

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")


class Config:
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg://payments:payments@localhost:5432/payments",
    )
    JWT_SECRET_KEY = os.environ.get(
        "JWT_SECRET_KEY", "local-development-secret-change-me-in-production"
    )
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    # Comma-separated browser origins allowed to call the API, e.g. the Swagger UI.
    CORS_ORIGINS = [origin for origin in os.environ.get("CORS_ORIGINS", "").split(",") if origin]
    CELERY = {
        "broker_url": REDIS_URL,
        "broker_connection_retry_on_startup": True,
        "task_ignore_result": True,
        "imports": ("src.infrastructure.tasks.payment_tasks",),
        "beat_schedule": {
            "requeue-stale-payments": {
                "task": "src.infrastructure.tasks.payment_tasks.requeue_stale_payments",
                "schedule": 60.0,
            },
        },
    }


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+psycopg://payments:payments@localhost:5432/payments_test",
    )
