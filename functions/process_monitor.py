"""
Моніторинг процесів: запис у БД (ProcessRun) для відображення в веб-адмінці.
Використовується в Celery-тасках для логування старту/успіху/помилки та історії логів.
"""

import contextvars
import logging
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Generator, List, Optional

from database.db import SessionLocal
from database.models import ProcessRun

logger = logging.getLogger(__name__)

# Поточний run_id для поточної таски (зв'язує логи з ProcessRun)
_current_run_id: contextvars.ContextVar[Optional[int]] = contextvars.ContextVar(
    "process_run_id", default=None
)

MAX_LOG_ENTRIES_PER_RUN = 2000

TASK_NAMES = {
    "process_link_car_urls": "Парсинг після додавання посилання",
    "recheck_processed_links": "Планова перевірка to_create/to_delete",
    "process_links_to_delete": "Видалення з TruckMarket (links_to_delete)",
    "process_car_add_truck_market": "Додавання авто на TruckMarket",
    "parse_links_to_create": "Парсер по links_to_create",
    "delete_link": "Видалення посилання з сайту та БД",
    "db_dump": "Щоденний дамп БД (09:00 Київ)",
}


def start_process_run(
    task_name: str,
    celery_task_id: Optional[str] = None,
    **details: Any,
) -> Optional[int]:
    """Записує старт процесу в БД. Повертає run_id або None при помилці."""
    db = SessionLocal()
    try:
        run = ProcessRun(
            task_name=task_name,
            status="running",
            started_at=datetime.utcnow(),
            details=details if details else None,
            celery_task_id=celery_task_id,
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        run_id = run.id
        logger.info("[%s] Started run_id=%s details=%s", task_name, run_id, details)
        return run_id
    except Exception as e:
        logger.exception("[%s] Failed to log start: %s", task_name, e)
        db.rollback()
        return None
    finally:
        db.close()


def finish_process_run(
    run_id: Optional[int],
    success: bool,
    message: Optional[str] = None,
    **details: Any,
) -> None:
    """Оновлює запис процесу: status=success/failed, finished_at, message, details."""
    if run_id is None:
        return
    db = SessionLocal()
    try:
        run = db.query(ProcessRun).filter(ProcessRun.id == run_id).first()
        if not run:
            logger.warning("[process_monitor] run_id=%s not found", run_id)
            return
        run.status = "success" if success else "failed"
        run.finished_at = datetime.utcnow()
        run.message = message
        if details:
            run.details = (run.details or {}) | details
        db.commit()
        logger.info(
            "[%s] Finished run_id=%s status=%s message=%s",
            run.task_name,
            run_id,
            run.status,
            message,
        )
    except Exception as e:
        logger.exception("[process_monitor] Failed to log finish run_id=%s: %s", run_id, e)
        db.rollback()
    finally:
        db.close()


def append_process_log(run_id: Optional[int], level: str, message: str) -> None:
    """Додає один запис до історії логів ProcessRun. Не використовує logger, щоб уникнути рекурсії."""
    if run_id is None:
        return
    db = SessionLocal()
    try:
        run = db.query(ProcessRun).filter(ProcessRun.id == run_id).first()
        if not run:
            return
        entry = {
            "t": datetime.utcnow().isoformat() + "Z",
            "level": level,
            "msg": message[: 8 * 1024],  # обмеження довжини повідомлення
        }
        logs: List[dict] = list(run.logs or [])
        logs.append(entry)
        if len(logs) > MAX_LOG_ENTRIES_PER_RUN:
            logs = logs[-MAX_LOG_ENTRIES_PER_RUN:]
        run.logs = logs
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


class TaskLogHandler(logging.Handler):
    """Handler, що записує логи поточного таска в ProcessRun.logs (run_id з contextvar)."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            run_id = _current_run_id.get()
            if run_id is None:
                return
            msg = self.format(record)
            level = record.levelname or "INFO"
            append_process_log(run_id, level, msg)
        except Exception:
            self.handleError(record)


def set_current_run_id(run_id: Optional[int]) -> None:
    """Встановити run_id поточної таски (для захоплення логів)."""
    _current_run_id.set(run_id)


def clear_current_run_id() -> None:
    """Очистити run_id після завершення таски."""
    try:
        _current_run_id.set(None)
    except LookupError:
        pass


def get_task_log_handler() -> TaskLogHandler:
    """Повертає handler для прив'язки до logger під час виконання таски."""
    h = TaskLogHandler()
    h.setLevel(logging.DEBUG)
    h.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    return h


# Логери, з яких збираємо логи в ProcessRun.logs (без root — щоб не засипати БД і консоль SQLAlchemy)
_TASK_LOG_LOGGER_NAMES = ("functions.celery_tasks", "app.scraper")


@contextmanager
def capture_task_logs(run_id: Optional[int]) -> Generator[None, None, None]:
    """Контекстний менеджер: під час виконання логи з наших логерів пишуться в ProcessRun.logs."""
    if run_id is None:
        yield
        return
    handler = get_task_log_handler()
    loggers = [logging.getLogger(name) for name in _TASK_LOG_LOGGER_NAMES]
    for log in loggers:
        log.addHandler(handler)
    set_current_run_id(run_id)
    try:
        yield
    finally:
        for log in loggers:
            log.removeHandler(handler)
        clear_current_run_id()
