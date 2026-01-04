from celery import Celery

celery_app = Celery(
    "autoria",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/1",
)

celery_app.conf.timezone = "UTC"

celery_app.autodiscover_tasks([
    "app.scraper",   # де лежать твої tasks
])
