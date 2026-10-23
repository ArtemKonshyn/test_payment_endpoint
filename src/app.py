import logging

from src.config import Config
from src.create_app import create_app

logging.basicConfig(level=logging.INFO)

app = create_app(Config())
celery_app = app.extensions["celery"]
