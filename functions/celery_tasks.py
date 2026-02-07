"""
Логіка Celery-тасків: винесена з tasks/config.py.
Викликається з tasks.config (тонкі обгортки).
"""

import logging
import os
import random
import subprocess
import time
from datetime import datetime
from urllib.parse import urlparse, unquote

from playwright.sync_api import sync_playwright

from database.db import SessionLocal
from database.models import (
    Car,
    Link,
    LinkParseStatus,
    LinkToCreate,
    LinkToDelete,
    StatusProcessed,
    StatusLinkChange,
)
from app.scraper.scraper_service import get_all_car_links
from app.scraper.main import parse_car
from functions.function import (
    check_update_link_status,
    TruckMarket,
    TruckMarketTokenProvider,
)
from functions.process_monitor import (
    capture_task_logs,
    finish_process_run,
    start_process_run,
)

logger = logging.getLogger(__name__)


def run_process_link_car_urls(link_id: int) -> dict:
    """
    Після додавання лінка через web: збирає car URL зі сторінок,
    оновлює links_to_create/links_to_delete, ставить parse_status=PARSED.
    """
    run_id = start_process_run("process_link_car_urls", link_id=link_id)
    with capture_task_logs(run_id):
        db = SessionLocal()
        try:
            link_obj = db.query(Link).filter(Link.id == link_id).first()
            if not link_obj:
                logger.warning("[process_link_car_urls] link_id=%s not found", link_id)
                finish_process_run(run_id, False, message="Link not found")
                return {"status": "error", "message": "Link not found"}
            logger.info("[process_link_car_urls] link_id=%s url=%s", link_id, link_obj.link)
            parsed_links = get_all_car_links(link_obj.link)
            check_update_link_status(link_obj.link, parsed_links)
            link_obj.parse_status = LinkParseStatus.PARSED
            link_obj.last_processed_at = datetime.utcnow()
            db.commit()
            msg = f"Зібрано {len(parsed_links)} car URL"
            logger.info("[process_link_car_urls] link_id=%s done, %s car URLs", link_id, len(parsed_links))
            finish_process_run(run_id, True, message=msg, car_urls_count=len(parsed_links))
            return {"status": "ok", "link_id": link_id, "car_urls_count": len(parsed_links)}
        except Exception as e:
            logger.exception("[process_link_car_urls] link_id=%s error: %s", link_id, e)
            db.rollback()
            finish_process_run(run_id, False, message=str(e))
            try:
                db2 = SessionLocal()
                link_obj = db2.query(Link).filter(Link.id == link_id).first()
                if link_obj:
                    link_obj.parse_status = LinkParseStatus.PARSED
                    link_obj.last_processed_at = datetime.utcnow()
                    db2.commit()
                db2.close()
            except Exception:
                pass
            return {"status": "error", "link_id": link_id, "message": str(e)}
        finally:
            db.close()


def run_recheck_processed_links() -> str:
    """Планова перевірка to_create/to_delete: для всіх PARSED links. Понеділок 00–03."""
    run_id = start_process_run("recheck_processed_links")
    with capture_task_logs(run_id):
        db = SessionLocal()
        try:
            link_objs = (
                db.query(Link).filter(Link.parse_status == LinkParseStatus.PARSED).all()
            )
            if not link_objs:
                logger.info("[recheck_processed_links] No PARSED links to recheck")
                finish_process_run(run_id, True, message="Немає PARSED links")
                return "No PARSED links"
            for link_obj in link_objs:
                try:
                    logger.info("[recheck_processed_links] link_id=%s url=%s", link_obj.id, link_obj.link)
                    time.sleep(random.uniform(1, 10))
                    parsed_links = get_all_car_links(link_obj.link)
                    check_update_link_status(link_obj.link, parsed_links)
                    link_obj.last_processed_at = datetime.utcnow()
                    link_obj.last_recheck_at = datetime.utcnow()
                    db.commit()
                except Exception as e:
                    logger.error("[recheck_processed_links] link_id=%s error: %s", link_obj.id, e)
                    db.rollback()
                    continue
            msg = f"Перевірено {len(link_objs)} посилань"
            finish_process_run(run_id, True, message=msg, links_count=len(link_objs))
            return msg
        except Exception as e:
            logger.exception("[recheck_processed_links] error: %s", e)
            finish_process_run(run_id, False, message=str(e))
            raise
        finally:
            db.close()


def run_process_links_to_delete() -> str:
    """links_to_delete (PROCESS) -> TruckMarket delete. Щогодини."""
    run_id = start_process_run("process_links_to_delete")
    with capture_task_logs(run_id):
        db = SessionLocal()
        truck_api = TruckMarket(TruckMarketTokenProvider())
        try:
            links_to_delete = (
                db.query(LinkToDelete)
                .filter(LinkToDelete.status == StatusLinkChange.PROCESS)
                .all()
            )
            if not links_to_delete:
                logger.info("[process_links_to_delete] No PROCESS records")
                finish_process_run(run_id, True, message="Немає записів у черзі")
                return "No links to delete"
            processed = 0
            for ltd in links_to_delete:
                logger.info("[process_links_to_delete] ltd_id=%s link=%s", ltd.id, ltd.link)
                try:
                    car = db.query(Car).filter(Car.link_path == ltd.link).first()
                    if not car:
                        logger.warning("No car found for link_to_delete.link=%s", ltd.link)
                        ltd.status = StatusLinkChange.COMPLETED
                        db.commit()
                        continue
                    if not car.truck_car_id:
                        logger.warning(
                            "Car %s has no truck_car_id, skipping delete", car.id
                        )
                        ltd.status = StatusLinkChange.COMPLETED
                        db.commit()
                        continue
                    try:
                        truck_api.delete_car_by_id(car.truck_car_id)
                    except Exception as api_err:
                        status_code = getattr(
                            getattr(api_err, "response", None), "status_code", None
                        )
                        if status_code == 404:
                            logger.warning(
                                "TruckMarket listing already deleted for car %s (truck_car_id=%s): %s",
                                car.id,
                                car.truck_car_id,
                                api_err,
                            )
                            car.processed_status = StatusProcessed.DELETED
                            ltd.status = StatusLinkChange.COMPLETED
                            db.commit()
                            processed += 1
                            continue
                        logger.error(
                            "TruckMarket delete_car_by_id failed for car %s (truck_car_id=%s): %s",
                            car.id,
                            car.truck_car_id,
                            api_err,
                        )
                        db.rollback()
                        continue
                    car.processed_status = StatusProcessed.DELETED
                    ltd.status = StatusLinkChange.COMPLETED
                    db.commit()
                    processed += 1
                except Exception as e:
                    logger.error(
                        "Error processing link to delete (id=%s, link=%s): %s",
                        ltd.id,
                        ltd.link,
                        e,
                    )
                    db.rollback()
                    continue
            msg = f"Оброблено {processed} записів"
            finish_process_run(run_id, True, message=msg, processed=processed)
            return msg
        except Exception as e:
            logger.exception("[process_links_to_delete] error: %s", e)
            finish_process_run(run_id, False, message=str(e))
            raise
        finally:
            db.close()


def run_delete_link(link_id: int) -> dict:
    """Видалення посилання: TruckMarket + БД. Викликається з веб (кнопка «Видалити посилання»)."""
    run_id = start_process_run("delete_link", link_id=link_id)
    with capture_task_logs(run_id):
        db = SessionLocal()
        try:
            link = db.query(Link).filter(Link.id == link_id).first()
            if not link:
                logger.warning("[delete_link] link_id=%s not found", link_id)
                finish_process_run(run_id, False, message="Link not found")
                return {"status": "error", "message": "Link not found"}
            cars_on_site = (
                db.query(Car)
                .filter(Car.link_id == link_id, Car.truck_car_id.isnot(None))
                .all()
            )
            deleted_from_site = 0
            if cars_on_site:
                truck_api = TruckMarket(TruckMarketTokenProvider())
                for car in cars_on_site:
                    if car.truck_car_id is None:
                        continue
                    try:
                        truck_api.delete_car_by_id(car.truck_car_id)
                        deleted_from_site += 1
                    except Exception as api_err:
                        status_code = getattr(
                            getattr(api_err, "response", None), "status_code", None
                        )
                        if status_code == 404:
                            deleted_from_site += 1
                            continue
                        logger.error(
                            "[delete_link] car_id=%s truck_car_id=%s api_err=%s",
                            car.id,
                            car.truck_car_id,
                            api_err,
                        )
                        raise
            db.delete(link)
            db.commit()
            msg = f"Посилання видалено. З сайту: {deleted_from_site} авто"
            logger.info("[delete_link] link_id=%s deleted_from_site=%s", link_id, deleted_from_site)
            finish_process_run(run_id, True, message=msg, deleted_from_site=deleted_from_site)
            return {
                "status": "ok",
                "message": msg,
                "deleted_from_site": deleted_from_site,
            }
        except Exception as e:
            db.rollback()
            logger.exception("[delete_link] link_id=%s failed: %s", link_id, e)
            finish_process_run(run_id, False, message=str(e))
            return {"status": "error", "message": str(e)}
        finally:
            db.close()


def run_parse_links_to_create() -> str:
    """Парсер по links_to_create: парсить сторінки авто, зберігає Car (CREATED). Вт–нд 03–06."""
    run_id = start_process_run("parse_links_to_create")
    with capture_task_logs(run_id):
        db = SessionLocal()
        try:
            to_create = (
                db.query(LinkToCreate)
                .filter(LinkToCreate.status == StatusLinkChange.PROCESS)
                .all()
            )
            if not to_create:
                logger.info("[parse_links_to_create] No PROCESS records")
                finish_process_run(run_id, True, message="Немає записів у черзі")
                return "No links_to_create to parse"
            # Отримуємо parent_link (URL) для кожного запису
            parent_link_ids = {ltc.parent_link_id for ltc in to_create}
            parents = {
                row.id: row.link
                for row in db.query(Link).filter(Link.id.in_(parent_link_ids)).all()
            }
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, slow_mo=40)
                context = browser.new_context(
                    locale="uk-UA",
                    viewport={"width": 1366, "height": 768},
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    ),
                )
                page = context.new_page()
                parsed = 0
                for ltc in to_create:
                    parent_link = parents.get(ltc.parent_link_id)
                    if not parent_link:
                        logger.warning(
                            "Parent link id=%s not found for link_to_create id=%s",
                            ltc.parent_link_id,
                            ltc.id,
                        )
                        continue
                    try:
                        logger.info("[parse_links_to_create] ltc_id=%s link=%s", ltc.id, ltc.link)
                        parse_car(page, ltc.link, parent_link)
                        ltc.status = StatusLinkChange.COMPLETED
                        db.commit()
                        parsed += 1
                    except Exception as e:
                        logger.exception("[parse_links_to_create] ltc_id=%s error: %s", ltc.id, e)
                        db.rollback()
                        continue
                    time.sleep(random.uniform(1, 5))
                browser.close()
            msg = f"Спарсено {parsed} авто"
            finish_process_run(run_id, True, message=msg, parsed=parsed)
            return msg
        except Exception as e:
            logger.exception("[parse_links_to_create] error: %s", e)
            finish_process_run(run_id, False, message=str(e))
            raise
        finally:
            db.close()


def run_process_car_add_truck_market() -> None:
    """Авто CREATED -> TruckMarket (create + images), ACTIVE/FAILED. Щогодини."""
    run_id = start_process_run("process_car_add_truck_market")
    with capture_task_logs(run_id):
        db = SessionLocal()
        truck_api = TruckMarket(TruckMarketTokenProvider())
        try:
            cars = (
                db.query(Car).filter(Car.processed_status == StatusProcessed.CREATED).all()
            )
            if not cars:
                logger.info("[process_car_add_truck_market] No CREATED cars")
                finish_process_run(run_id, True, message="Немає авто у черзі")
                return
            for car in cars:
                car.processed_status = StatusProcessed.PROCESS
            db.commit()
            processed_ok = 0
            for car in cars:
                try:
                    logger.info("[process_car_add_truck_market] car_id=%s %s %s", car.id, car.brand, car.model)
                    ok = truck_api.process_add_car(car)
                    if ok:
                        processed_ok += 1
                    else:
                        logger.error("[process_car_add_truck_market] add_car failed car_id=%s", car.id)
                        truck_api._set_car_status(car.id, StatusProcessed.FAILED)
                except Exception as e:
                    logger.exception("[process_car_add_truck_market] car_id=%s error: %s", car.id, e)
                    truck_api._set_car_status(car.id, StatusProcessed.FAILED)
                    continue
            msg = f"Оброблено {processed_ok}/{len(cars)} авто"
            finish_process_run(run_id, True, message=msg, processed=processed_ok, total=len(cars))
        except Exception as e:
            logger.exception("[process_car_add_truck_market] error: %s", e)
            finish_process_run(run_id, False, message=str(e))
            raise
        finally:
            db.close()


def run_db_dump() -> str:
    """Щодня о 09:00 (Київ): дамп PostgreSQL через pg_dump у файл у BACKUP_DIR (за замовчуванням /app/backups)."""
    run_id = start_process_run("db_dump")
    with capture_task_logs(run_id):
        try:
            db_url = os.getenv("DATABASE_PRODUCTION_URI")
            if not db_url or "postgresql" not in db_url:
                msg = "DATABASE_DEVELOPMENT_URI не задано або не PostgreSQL"
                logger.warning("[db_dump] %s", msg)
                finish_process_run(run_id, False, message=msg)
                return msg
            parsed = urlparse(db_url)
            if parsed.scheme not in ("postgresql", "postgres"):
                msg = "Підтримується лише PostgreSQL"
                finish_process_run(run_id, False, message=msg)
                return msg
            host = parsed.hostname or "localhost"
            port = parsed.port or 5432
            user = unquote(parsed.username) if parsed.username else None
            password = unquote(parsed.password) if parsed.password else None
            dbname = (parsed.path or "").lstrip("/") or "postgres"
            if not user:
                msg = "У URL БД відсутній користувач"
                finish_process_run(run_id, False, message=msg)
                return msg
            backup_dir = os.getenv("BACKUP_DIR", "/app/backups")
            os.makedirs(backup_dir, exist_ok=True)
            date_str = datetime.now().strftime("%Y-%m-%d")
            out_path = os.path.join(backup_dir, f"autoria_dump_{date_str}.sql")
            env = os.environ.copy()
            if password:
                env["PGPASSWORD"] = password
            cmd = [
                "pg_dump",
                "-h", host,
                "-p", str(port),
                "-U", user,
                "-d", dbname,
                "-f", out_path,
                "--no-owner",
                "--no-acl",
            ]
            logger.info("[db_dump] running pg_dump -> %s", out_path)
            result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=600)
            if result.returncode != 0:
                msg = f"pg_dump failed: {result.stderr or result.stdout or 'unknown'}"
                logger.error("[db_dump] %s", msg)
                finish_process_run(run_id, False, message=msg)
                return msg
            size_mb = os.path.getsize(out_path) / (1024 * 1024)
            msg = f"Дамп збережено: {out_path} ({size_mb:.2f} MB)"
            logger.info("[db_dump] %s", msg)
            finish_process_run(run_id, True, message=msg, path=out_path, size_mb=round(size_mb, 2))
            return msg
        except subprocess.TimeoutExpired:
            msg = "pg_dump timeout (10 min)"
            logger.error("[db_dump] %s", msg)
            finish_process_run(run_id, False, message=msg)
            return msg
        except Exception as e:
            logger.exception("[db_dump] error: %s", e)
            finish_process_run(run_id, False, message=str(e))
            raise
