# celery_app.py

import os
from celery import Celery
from celery.schedules import schedule
from dotenv import load_dotenv
from datetime import timedelta

load_dotenv()

redis_url = os.getenv("REDIS_URL")
if not redis_url:
    raise RuntimeError("REDIS_URL not set")

celery_app = Celery(
    "worker",
    broker=redis_url,
    backend=redis_url,
    include=[
        "ai.tasks",
        "notification_service.tasks",  # додаємо наш новий модуль
    ],
)

# черги
celery_app.conf.task_routes = {
    "ai.tasks.analyze_message": {"queue": "ai_queue"},
    "notification_service.tasks.send_message": {"queue": "notification_queue"},
    "notification_service.tasks.dispatch_non_critical": {"queue": "notification_queue"},
}

# налаштування Beat (пакетна відправка кожні N хвилин)
interval = int(os.getenv("DISPATCH_INTERVAL_MINUTES", 5))
celery_app.conf.beat_schedule = {
    "dispatch-non-critical-every-n-minutes": {
        "task": "notification_service.tasks.dispatch_non_critical",
        "schedule": schedule(run_every=timedelta(minutes=interval)),
    },
}
