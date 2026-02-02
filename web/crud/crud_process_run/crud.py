"""CRUD для ProcessRun (моніторинг процесів)."""

from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any

from database.db import SessionLocal
from database.models import ProcessRun
from sqlalchemy import func


def get_process_run_by_id(run_id: int) -> Optional[ProcessRun]:
    """Отримати один запуск за ID (для сторінки деталей з логами)."""
    db = SessionLocal()
    try:
        return db.query(ProcessRun).filter(ProcessRun.id == run_id).first()
    finally:
        db.close()


def get_process_runs(
    task_name: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
) -> List[ProcessRun]:
    """Список запусків процесів з фільтрами."""
    db = SessionLocal()
    try:
        query = db.query(ProcessRun).order_by(ProcessRun.started_at.desc())
        if task_name:
            query = query.filter(ProcessRun.task_name == task_name)
        if status:
            query = query.filter(ProcessRun.status == status)
        return query.limit(limit).all()
    finally:
        db.close()


def get_process_run_stats() -> Dict[str, Any]:
    """Останній запуск по кожному типу тасків та кількість за 24 год."""
    db = SessionLocal()
    try:
        runs = (
            db.query(ProcessRun)
            .order_by(ProcessRun.started_at.desc())
            .limit(500)
            .all()
        )
        by_task = {}
        for r in runs:
            if r.task_name not in by_task:
                by_task[r.task_name] = r
        since = datetime.utcnow() - timedelta(hours=24)
        counts = (
            db.query(ProcessRun.status, func.count(ProcessRun.id))
            .filter(ProcessRun.started_at >= since)
            .group_by(ProcessRun.status)
            .all()
        )
        last_24h = {s: c for s, c in counts}
        return {"by_task": by_task, "last_24h": last_24h}
    finally:
        db.close()
