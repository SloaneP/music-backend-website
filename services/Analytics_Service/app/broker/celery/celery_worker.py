from celery import Celery, signals
from ...config import load_config
from ...database import db_initializer
import asyncio
import logging

cfg = load_config()
logger = logging.getLogger(cfg.SERVICE_NAME)

celery_app = Celery(
    "analytics",
    broker=cfg.REDIS_URL,
    backend=cfg.REDIS_URL,
    include=["app.broker.celery.tasks"]
)
celery_app.conf.timezone = "UTC"
