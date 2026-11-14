"""Celery: fon vazifalari va jadval (Beat). Server qayta ishga tushsa, jadval Redis/Beat orqali tiklanadi."""
from celery import Celery

from app.core.config import get_settings
from app.core.logging import setup_logging

settings = get_settings()
setup_logging(settings.log_level)

celery = Celery("smartagro", broker=settings.redis_url, backend=settings.redis_url, include=["app.workers.tasks"])
celery.conf.update(
    timezone="UTC",
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_time_limit=300,
    task_soft_time_limit=240,
    broker_connection_retry_on_startup=True,
    beat_schedule={
        # har 15 daqiqada hisobot vaqti kelgan dalalarni tanlaymiz (har fermerning o'z intervali bor)
        "dispatch-due-reports": {"task": "app.workers.tasks.dispatch_due_reports", "schedule": 15 * 60},
        "check-devices-offline": {"task": "app.workers.tasks.check_devices", "schedule": 15 * 60},
        "refresh-forecasts": {"task": "app.workers.tasks.refresh_all", "schedule": 60 * 60},
    },
)
