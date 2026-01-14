"""
Сервіс для запуску парсера з Flask API
"""
import logging
import threading
import time
import random
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from playwright.sync_api import sync_playwright, Page
from app.scraper.main import (
    pause, scroll, move_mouse, accept_cookies, get_links, parse_car
)

logger = logging.getLogger(__name__)


def update_page_in_url(url: str, page: int) -> str:
    """
    Оновлює або додає параметр page в URL.
    
    Args:
        url: Початковий URL
        page: Номер сторінки (починається з 0)
    
    Returns:
        URL з оновленим/доданим параметром page
    """
    parsed = urlparse(url)
    query_params = parse_qs(parsed.query)
    query_params['page'] = [str(page)]
    
    new_query = urlencode(query_params, doseq=True)
    new_url = urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        new_query,
        parsed.fragment
    ))
    return new_url


def run_scraper_for_link(parent_link: str, link_id: int):
    """
    Запускає парсер для конкретного батьківського лінка в окремому потоці.
    
    Args:
        parent_link: Батьківський лінк для парсингу
        link_id: ID лінка в БД
    """
    def _run():
        try:
            logger.info(f"Starting scraper for link_id={link_id}, url={parent_link}")
            
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

                logger.info("OPEN search page")
                page.goto(parent_link, wait_until="domcontentloaded", timeout=60000)

                pause(2, 4)
                scroll(page)
                move_mouse(page)

                accept_cookies(page)
                pause(2, 3)

                # Парсимо всі сторінки
                page_number = 0
                total_cars_parsed = 0
                
                while True:
                    # Оновлюємо URL з поточним номером сторінки
                    current_url = update_page_in_url(parent_link, page_number)
                    logger.info(f"PAGE {page_number}: Opening {current_url}")
                    
                    page.goto(current_url, wait_until="domcontentloaded", timeout=60000)
                    pause(2, 4)
                    scroll(page)
                    move_mouse(page)
                    
                    # Отримуємо лінки на поточній сторінці
                    links = get_links(page)
                    
                    # Якщо на сторінці немає авто - закінчуємо парсинг
                    if not links or len(links) == 0:
                        logger.info(f"PAGE {page_number}: No cars found. Stopping scraper.")
                        break
                    
                    logger.info(f"PAGE {page_number}: Found {len(links)} cars")
                    
                    # Парсимо всі авто на поточній сторінці
                    for i, car_link in enumerate(links, 1):
                        total_cars_parsed += 1
                        logger.info(f"PAGE {page_number}, CAR {i}/{len(links)} (Total: {total_cars_parsed})")
                        try:
                            parse_car(page, car_link, parent_link)
                        except Exception as e:
                            logger.exception("CRASH on %s: %s", car_link, e)

                        pause(3, 6)
                        scroll(page, 2)
                    
                    # Переходимо на наступну сторінку
                    page_number += 1
                    pause(2, 4)  # Невелика пауза між сторінками

                browser.close()
                logger.info(f"Scraper finished for link_id={link_id}. Total pages: {page_number}, Total cars: {total_cars_parsed}")
                
        except Exception as e:
            logger.exception(f"Error in scraper for link_id={link_id}: {e}")
    
    # Запускаємо в окремому потоці
    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return thread

