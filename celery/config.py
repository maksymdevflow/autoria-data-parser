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

celery_app = Celery(
    "autoria",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/1",
)

celery_app.conf.timezone = "UTC"
celery_app.conf.task_routes = {
    'celery.config.process_unpublished_cars': {'queue': 'unpublished'},
    'celery.config.scrape_parent_link': {'queue': 'scraping'},
}


@celery_app.task(name='celery.config.process_unpublished_cars', bind=False)
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


@celery_app.task(name='celery.config.scrape_parent_link', bind=True)
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
        from app.scraper.main import (
            pause, scroll, move_mouse, accept_cookies, get_links, parse_car
        )
        from app.scraper.scraper_service import update_page_in_url
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


celery_app.conf.beat_schedule = {
    "process-unpublished-cars-every-45-min": {
        "task": "celery.config.process_unpublished_cars",
        "schedule": crontab(minute="*/45"),  # Кожні 45 хвилин
    },
}
