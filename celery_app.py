import os
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

redis_url = os.getenv("REDIS_URL")
if not redis_url:
    raise RuntimeError("REDIS_URL not set")

celery_app = Celery(
    "worker",
    broker=redis_url,
    backend=redis_url,
    include=["ai.tasks"],
)

# (за бажанням) конфігурація черг
celery_app.conf.task_routes = {
    "ai.tasks.analyze_message": {"queue": "ai_queue"},
}
