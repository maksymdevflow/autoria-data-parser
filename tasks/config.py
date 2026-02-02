"""
Celery app та розклад: 4 таски.
Логіка тасків у functions.celery_tasks.
"""

import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import importlib.util

spec = importlib.util.find_spec("app")
if spec is None and project_root not in sys.path:
    sys.path.insert(0, project_root)

from celery import Celery
from celery.schedules import crontab

from functions.celery_tasks import (
    run_process_link_car_urls,
    run_recheck_processed_links,
    run_process_links_to_delete,
    run_process_car_add_truck_market,
    run_parse_links_to_create,
    run_delete_link,
    run_db_dump,
)

def _is_full_redis_url(url: str) -> bool:
    """URL має бути redis://host або rediss://host (не просто redis://)."""
    if not url or len(url.strip()) <= 8:
        return False
    u = url.strip()
    return (u.startswith("redis://") or u.startswith("rediss://")) and u not in ("redis://", "rediss://", "redis:///", "rediss:///")

_broker_raw = (
    os.getenv("CELERY_BROKER_URL")
    or os.getenv("REDIS_DEVELOPMENT_URI")
    or "redis://localhost:6379/0"
)
# Broker: лише повний URL з hostname (redis:// без host дає "No hostname was supplied" і 500)
_celery_broker = _broker_raw if _is_full_redis_url(_broker_raw) else "redis://localhost:6379/0"
# Backend: лише повний redis:// URL (Celery інакше парсить "redis/1" як module.attribute і падає)
_env_backend = os.getenv("CELERY_RESULT_BACKEND")
if _env_backend and _is_full_redis_url(_env_backend):
    _celery_backend = _env_backend
elif _is_full_redis_url(_celery_broker):
    _celery_backend = _celery_broker.rstrip("/0").rstrip("/") + "/1"
else:
    _celery_backend = "redis://localhost:6379/1"

celery_app = Celery(
    "autoria",
    broker=_celery_broker,
    backend=_celery_backend,
)

# Розклад у часі Києва (Europe/Kiev)
celery_app.conf.timezone = "Europe/Kiev"
celery_app.conf.enable_utc = False
celery_app.conf.worker_pool = "solo"
celery_app.conf.worker_concurrency = 1

# add to TruckMarket | recheck to_create/to_delete (пон 00–03) | parse after web (on demand) | delete | parse to_create (вт–нд 3–6) | hourly TruckMarket
celery_app.conf.task_routes = {
    "tasks.config.process_car_add_truck_market": {"queue": "truck_market"},
    "tasks.config.recheck_processed_links": {"queue": "parent_links"},
    "tasks.config.process_link_car_urls": {"queue": "parent_links"},
    "tasks.config.process_links_to_delete": {"queue": "truck_market"},
    "tasks.config.parse_links_to_create": {"queue": "parent_links"},
    "tasks.config.db_dump": {"queue": "parent_links"},
}

# Europe/Kiev: понеділок 00–03 recheck; вт–нд 03–06 парсинг; щогодини TruckMarket; щодня 09:00 дамп БД.
celery_app.conf.beat_schedule = {
    "recheck_processed_links_monday": {
        "task": "tasks.config.recheck_processed_links",
        "schedule": crontab(minute=0, hour="0-2", day_of_week=1),
    },
    "parse_links_to_create_03_06": {
        "task": "tasks.config.parse_links_to_create",
        "schedule": crontab(minute=0, hour="3-6", day_of_week="0,2-6"),
    },
    "process_car_add_truck_market_hourly": {
        "task": "tasks.config.process_car_add_truck_market",
        "schedule": crontab(minute=0),
    },
    "process_links_to_delete_hourly": {
        "task": "tasks.config.process_links_to_delete",
        "schedule": crontab(minute=0),
    },
    "db_dump_daily": {
        "task": "tasks.config.db_dump",
        "schedule": crontab(minute=0, hour=9),
    },
}


@celery_app.task(name="tasks.config.process_link_car_urls")
def process_link_car_urls(link_id: int):
    """Парсинг після додавання лінка через web (однопоточний, по черзі parent_links)."""
    return run_process_link_car_urls(link_id)


@celery_app.task(name="tasks.config.recheck_processed_links")
def recheck_processed_links():
    """Понеділок 00:00–03:00: перевірка to_create/to_delete по вже спарсених links."""
    return run_recheck_processed_links()


@celery_app.task(name="tasks.config.process_links_to_delete")
def process_links_to_delete():
    """Щогодини: видалення з TruckMarket за links_to_delete."""
    return run_process_links_to_delete()


@celery_app.task(name="tasks.config.parse_links_to_create")
def parse_links_to_create():
    """Вт–нд 03:00–06:00: парсер по links_to_create, парсить сторінки авто, зберігає Car (CREATED)."""
    return run_parse_links_to_create()


@celery_app.task(name="tasks.config.process_car_add_truck_market")
def process_car_add_truck_market():
    """Щогодини: додавання авто (CREATED) на TruckMarket по інтеграції."""
    return run_process_car_add_truck_market()


@celery_app.task(name="tasks.config.delete_link")
def delete_link(link_id: int):
    """Видалення лінка з сайту (TruckMarket) та з БД. Викликається з веб-інтерфейсу."""
    return run_delete_link(link_id)


@celery_app.task(name="tasks.config.db_dump")
def db_dump():
    """Щодня о 09:00 (Київ): дамп PostgreSQL у файл."""
    return run_db_dump()

