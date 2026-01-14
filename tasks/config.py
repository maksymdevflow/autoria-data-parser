import sys
import os
from datetime import datetime, timedelta
from celery import Celery
from celery.schedules import crontab
from database.db import SessionLocal
from database.models import Car, Link, StatusProcessed
from sqlalchemy import func

# Додаємо корінь проекту до шляху
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Переконаємося, що всі необхідні модулі доступні
import importlib.util
spec = importlib.util.find_spec("app")
if spec is None:
    # Якщо модуль app не знайдено, додаємо шлях ще раз
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

celery_app = Celery(
    "autoria",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/1",
)

celery_app.conf.timezone = "UTC"
# Використовуємо solo pool для Windows (prefork не працює на Windows)
celery_app.conf.worker_pool = "solo"
celery_app.conf.worker_concurrency = 1
celery_app.conf.task_routes = {
    'tasks.config.process_unpublished_cars': {'queue': 'unpublished'},
    'tasks.config.scrape_parent_link': {'queue': 'scraping'},  # Черга для додавання/парсингу
    'tasks.config.parse_single_car': {'queue': 'scraping'},  # Парсинг одного авто
    'tasks.config.delete_cars': {'queue': 'deletion'},  # Черга для видалення
    'tasks.config.sync_all_parent_links': {'queue': 'unpublished'},  # Синхронізація всіх лінків
    'tasks.config.sync_single_parent_link': {'queue': 'unpublished'},  # Синхронізація одного лінка
}


@celery_app.task(name='tasks.config.process_unpublished_cars', bind=False)
def process_unpublished_cars():
    """
    Обробляє всі неопубліковані авто.
    Заглушка - просто логує інформацію.
    """
    db = SessionLocal()
    try:
        # Отримуємо всі неопубліковані авто
        unpublished_cars = db.query(Car).filter(
            Car.is_published == False
        ).all()
        
        # Заглушка - просто логуємо
        print(f"[PROCESS UNPUBLISHED] Found {len(unpublished_cars)} unpublished cars")
        for car in unpublished_cars:
            print(f"[PROCESS UNPUBLISHED] Car ID: {car.id}, Brand: {car.brand}, Status: {car.processed_status}")
            # Тут буде логіка обробки неопублікованих авто
        
        return {
            "processed": len(unpublished_cars),
            "message": f"Processed {len(unpublished_cars)} unpublished cars"
        }
    finally:
        db.close()


@celery_app.task(name='tasks.config.scrape_parent_link', bind=True)
def scrape_parent_link(self, parent_link: str, link_id: int):
    """
    Парсить батьківський лінк.
    Має обмеження: максимум 2 батьківські лінки в день.
    """
    db = SessionLocal()
    try:
        # Перевіряємо скільки лінків вже створено сьогодні (для обмеження 2 в день)
        today = datetime.utcnow().date()
        today_start = datetime.combine(today, datetime.min.time())
        
        links_created_today = db.query(func.count(Link.id)).filter(
            Link.created_at >= today_start
        ).scalar()
        
        if links_created_today >= 2:
            print(f"[SCRAPE LINK] Daily limit reached: {links_created_today}/2 links created today")
            return {
                "status": "limit_reached",
                "message": f"Daily limit reached: {links_created_today}/2 links created today. Try again tomorrow."
            }
        
        # Запускаємо парсер напряму (без threading, бо вже в Celery воркері)
        # Додаємо шлях до проекту для імпортів (важливо для Celery воркера)
        current_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if current_project_root not in sys.path:
            sys.path.insert(0, current_project_root)
        
        # Перевіряємо, чи модуль доступний
        try:
            from app.scraper.main import (
                pause, scroll, move_mouse, accept_cookies, get_links, parse_car
            )
            from app.scraper.scraper_service import update_page_in_url
        except ImportError as e:
            print(f"[SCRAPE LINK] Import error: {e}")
            print(f"[SCRAPE LINK] sys.path: {sys.path[:3]}")
            print(f"[SCRAPE LINK] project_root: {current_project_root}")
            raise
        from playwright.sync_api import sync_playwright
        import logging
        
        logger = logging.getLogger(__name__)
        logger.info(f"[SCRAPE LINK] Starting scraper for link_id={link_id}, url={parent_link}")
        
        # Запускаємо парсер напряму
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, slow_mo=40)
            context = browser.new_context(
                locale="uk-UA",
                viewport={"width": 1366, "height": 768},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            )
            
            page = context.new_page()
            
            # Парсимо всі сторінки
            page_number = 0
            total_cars_parsed = 0
            
            while True:
                current_url = update_page_in_url(parent_link, page_number)
                logger.info(f"PAGE {page_number}: Opening {current_url}")
                
                page.goto(current_url, wait_until="domcontentloaded", timeout=60000)
                pause(2, 4)
                scroll(page)
                move_mouse(page)
                
                accept_cookies(page)
                pause(2, 3)
                
                links = get_links(page)
                
                if not links or len(links) == 0:
                    logger.info(f"PAGE {page_number}: No cars found. Stopping scraper.")
                    break
                
                logger.info(f"PAGE {page_number}: Found {len(links)} cars")
                
                for i, car_link in enumerate(links, 1):
                    total_cars_parsed += 1
                    logger.info(f"PAGE {page_number}, CAR {i}/{len(links)} (Total: {total_cars_parsed})")
                    try:
                        parse_car(page, car_link, parent_link)
                    except Exception as e:
                        logger.exception("CRASH on %s: %s", car_link, e)
                    
                    pause(3, 6)
                    scroll(page, 2)
                
                page_number += 1
                pause(2, 4)
            
            browser.close()
            logger.info(f"Scraper finished for link_id={link_id}. Total pages: {page_number}, Total cars: {total_cars_parsed}")
        
        # Оновлюємо last_processed_at
        link = db.query(Link).filter(Link.id == link_id).first()
        if link:
            link.last_processed_at = datetime.utcnow()
            db.commit()
        
        return {
            "status": "completed",
            "link_id": link_id,
            "pages": page_number,
            "cars_parsed": total_cars_parsed,
            "message": f"Scraper completed: {total_cars_parsed} cars from {page_number} pages"
        }
    except Exception as e:
        print(f"[SCRAPE LINK] Error: {str(e)}")
        raise
    finally:
        db.close()


@celery_app.task(name='tasks.config.parse_single_car', bind=True)
def parse_single_car(self, car_link: str, parent_link: str, link_id: int):
    """
    Парсить одне авто за посиланням.
    Використовується при синхронізації для додавання нових авто.
    
    Args:
        car_link: Посилання на авто
        parent_link: Батьківський лінк
        link_id: ID батьківського лінка
    """
    try:
        # Додаємо шлях до проекту для імпортів
        current_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if current_project_root not in sys.path:
            sys.path.insert(0, current_project_root)
        
        from app.scraper.main import parse_car
        from playwright.sync_api import sync_playwright
        import logging
        
        logger = logging.getLogger(__name__)
        logger.info(f"[PARSE SINGLE CAR] Parsing car: {car_link}")
        
        # Запускаємо парсер для одного авто
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, slow_mo=40)
            context = browser.new_context(
                locale="uk-UA",
                viewport={"width": 1366, "height": 768},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            )
            
            page = context.new_page()
            
            try:
                parse_car(page, car_link, parent_link)
                logger.info(f"[PARSE SINGLE CAR] Successfully parsed: {car_link}")
            except Exception as e:
                logger.exception(f"[PARSE SINGLE CAR] Error parsing {car_link}: {e}")
                raise
            finally:
                browser.close()
        
        return {
            "status": "completed",
            "car_link": car_link,
            "link_id": link_id
        }
    except Exception as e:
        logger.exception(f"[PARSE SINGLE CAR] Error: {e}")
        raise


@celery_app.task(name='tasks.config.delete_cars', bind=True)
def delete_cars(self, car_ids: list = None, link_id: int = None):
    """
    Видаляє авто з бази даних.
    Поки що заглушка - просто логує інформацію.
    
    Args:
        car_ids: Список ID авто для видалення (опціонально)
        link_id: ID батьківського лінка - видалити всі авто цього лінка (опціонально)
    """
    db = SessionLocal()
    try:
        # Додаємо шлях до проекту для імпортів
        current_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if current_project_root not in sys.path:
            sys.path.insert(0, current_project_root)
        
        print(f"[DELETE CARS] Starting deletion process")
        print(f"[DELETE CARS] car_ids: {car_ids}, link_id: {link_id}")
        
        # Заглушка - поки що просто логуємо
        if car_ids:
            cars_to_delete = db.query(Car).filter(Car.id.in_(car_ids)).all()
            print(f"[DELETE CARS] Found {len(cars_to_delete)} cars to delete by IDs")
            for car in cars_to_delete:
                print(f"[DELETE CARS] Would delete Car ID: {car.id}, Brand: {car.brand}, Link: {car.link_path}")
        
        if link_id:
            cars_to_delete = db.query(Car).filter(Car.link_id == link_id).all()
            print(f"[DELETE CARS] Found {len(cars_to_delete)} cars to delete by link_id={link_id}")
            for car in cars_to_delete:
                print(f"[DELETE CARS] Would delete Car ID: {car.id}, Brand: {car.brand}, Link: {car.link_path}")
        
        # Тут буде логіка видалення:
        # if car_ids:
        #     db.query(Car).filter(Car.id.in_(car_ids)).delete(synchronize_session=False)
        # if link_id:
        #     db.query(Car).filter(Car.link_id == link_id).delete(synchronize_session=False)
        # db.commit()
        
        return {
            "status": "pending",
            "message": "Deletion task received (stub - not implemented yet)",
            "car_ids": car_ids,
            "link_id": link_id
        }
    except Exception as e:
        print(f"[DELETE CARS] Error: {str(e)}")
        raise
    finally:
        db.close()


@celery_app.task(name='tasks.config.sync_all_parent_links', bind=False)
def sync_all_parent_links():
    """
    Синхронізує всі батьківські лінки.
    Запускається раз на тиждень через Celery Beat.
    Для кожного лінка створює задачу sync_single_parent_link.
    """
    db = SessionLocal()
    try:
        # Додаємо шлях до проекту для імпортів
        current_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if current_project_root not in sys.path:
            sys.path.insert(0, current_project_root)
        
        # Отримуємо всі батьківські лінки
        all_links = db.query(Link).all()
        
        print(f"[SYNC ALL LINKS] Found {len(all_links)} parent links to sync")
        
        # Для кожного лінка створюємо задачу синхронізації
        for link in all_links:
            sync_single_parent_link.delay(link.id, link.link)
            print(f"[SYNC ALL LINKS] Queued sync for link_id={link.id}, url={link.link}")
        
        return {
            "status": "queued",
            "links_count": len(all_links),
            "message": f"Queued {len(all_links)} links for synchronization"
        }
    finally:
        db.close()


@celery_app.task(name='tasks.config.sync_single_parent_link', bind=True)
def sync_single_parent_link(self, link_id: int, parent_link: str):
    """
    Синхронізує один батьківський лінк:
    1. Отримує всі посилання авто з БД для цього лінка
    2. Парсить батьківський лінк і отримує список посилань
    3. Порівнює і створює задачі для додавання/видалення
    
    Args:
        link_id: ID батьківського лінка
        parent_link: URL батьківського лінка
    """
    db = SessionLocal()
    try:
        # Додаємо шлях до проекту для імпортів
        current_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if current_project_root not in sys.path:
            sys.path.insert(0, current_project_root)
        
        from app.scraper.main import (
            pause, scroll, move_mouse, accept_cookies, get_links
        )
        from app.scraper.scraper_service import update_page_in_url
        from playwright.sync_api import sync_playwright
        import logging
        
        logger = logging.getLogger(__name__)
        logger.info(f"[SYNC LINK] Starting sync for link_id={link_id}, url={parent_link}")
        
        # 1. Отримуємо всі посилання авто з БД для цього лінка
        db_car_links = set()
        cars_in_db = db.query(Car).filter(Car.link_id == link_id).all()
        for car in cars_in_db:
            db_car_links.add(car.link_path)
        
        logger.info(f"[SYNC LINK] Found {len(db_car_links)} cars in DB for link_id={link_id}")
        
        # 2. Парсимо батьківський лінк і отримуємо список посилань
        scraped_car_links = set()
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, slow_mo=40)
            context = browser.new_context(
                locale="uk-UA",
                viewport={"width": 1366, "height": 768},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            )
            
            page = context.new_page()
            
            # Парсимо всі сторінки
            page_number = 0
            
            while True:
                current_url = update_page_in_url(parent_link, page_number)
                logger.info(f"[SYNC LINK] PAGE {page_number}: Opening {current_url}")
                
                page.goto(current_url, wait_until="domcontentloaded", timeout=60000)
                pause(2, 4)
                scroll(page)
                move_mouse(page)
                
                accept_cookies(page)
                pause(2, 3)
                
                links = get_links(page)
                
                if not links or len(links) == 0:
                    logger.info(f"[SYNC LINK] PAGE {page_number}: No cars found. Stopping.")
                    break
                
                logger.info(f"[SYNC LINK] PAGE {page_number}: Found {len(links)} cars")
                
                # Додаємо посилання до множини
                for car_link in links:
                    scraped_car_links.add(car_link)
                
                page_number += 1
                pause(2, 4)
            
            browser.close()
        
        logger.info(f"[SYNC LINK] Scraped {len(scraped_car_links)} unique car links")
        
        # 3. Порівнюємо
        # Авто для додавання: є в scraped, немає в БД
        to_add = scraped_car_links - db_car_links
        
        # Авто для видалення: є в БД, немає в scraped
        to_delete = db_car_links - scraped_car_links
        
        logger.info(f"[SYNC LINK] To add: {len(to_add)}, To delete: {len(to_delete)}")
        
        # Створюємо задачі для додавання (парсинг кожного авто)
        added_count = 0
        for car_link in to_add:
            try:
                # Додаємо задачу в чергу scraping для парсингу цього авто
                parse_single_car.delay(car_link, parent_link, link_id)
                logger.info(f"[SYNC LINK] Queued parse for new car: {car_link}")
                added_count += 1
            except Exception as e:
                logger.exception(f"[SYNC LINK] Error queuing car {car_link}: {e}")
        
        # Створюємо задачі для видалення
        deleted_count = 0
        if to_delete:
            # Отримуємо ID авто для видалення
            cars_to_delete = db.query(Car).filter(
                Car.link_id == link_id,
                Car.link_path.in_(list(to_delete))
            ).all()
            
            car_ids_to_delete = [car.id for car in cars_to_delete]
            
            if car_ids_to_delete:
                delete_cars.delay(car_ids=car_ids_to_delete)
                deleted_count = len(car_ids_to_delete)
                logger.info(f"[SYNC LINK] Queued deletion for {deleted_count} cars")
        
        # Оновлюємо last_processed_at
        link = db.query(Link).filter(Link.id == link_id).first()
        if link:
            link.last_processed_at = datetime.utcnow()
            db.commit()
        
        return {
            "status": "completed",
            "link_id": link_id,
            "db_cars_count": len(db_car_links),
            "scraped_cars_count": len(scraped_car_links),
            "to_add": len(to_add),
            "to_delete": len(to_delete),
            "added_queued": added_count,
            "deleted_queued": deleted_count,
            "message": f"Sync completed: {len(to_add)} to add, {len(to_delete)} to delete"
        }
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.exception(f"[SYNC LINK] Error syncing link_id={link_id}: {e}")
        raise
    finally:
        db.close()


celery_app.conf.beat_schedule = {
    "process-unpublished-cars-every-45-min": {
        "task": "tasks.config.process_unpublished_cars",
        "schedule": crontab(minute="*/45"),  # Кожні 45 хвилин
    },
    "sync-all-parent-links-weekly": {
        "task": "tasks.config.sync_all_parent_links",
        "schedule": crontab(day_of_week=1, hour=2, minute=0),  # Кожен понеділок о 2:00
    },
}

