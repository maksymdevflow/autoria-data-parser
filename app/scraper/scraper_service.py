"""
Сервіс для запуску парсера з Flask API
"""

import logging
import threading
import time
import random
from datetime import datetime
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from playwright.sync_api import sync_playwright, Page
from app.scraper.main import (
    pause,
    scroll,
    move_mouse,
    accept_cookies,
    get_links,
    parse_car,
)
from database.db import SessionLocal
from database.models import Link

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
    query_params["page"] = [str(page)]

    new_query = urlencode(query_params, doseq=True)
    new_url = urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            new_query,
            parsed.fragment,
        )
    )
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
                        logger.info(
                            f"PAGE {page_number}: No cars found. Stopping scraper."
                        )
                        break

                    logger.info(f"PAGE {page_number}: Found {len(links)} cars")

                    # Парсимо всі авто на поточній сторінці
                    for i, car_link in enumerate(links, 1):
                        total_cars_parsed += 1
                        logger.info(
                            f"PAGE {page_number}, CAR {i}/{len(links)} (Total: {total_cars_parsed})"
                        )
                        try:
                            parse_car(page, car_link, parent_link)
                        except Exception as e:
                            logger.exception("CRASH on %s: %s", car_link, e)

                        # Затримка між посиланнями: рандомно від 1 до 5 секунд
                        pause(1, 5)

                        # Додаткова рандомна затримка від 1 до 10 секунд
                        additional_delay = random.uniform(1, 10)
                        time.sleep(additional_delay)
                        logger.debug(
                            f"Additional delay: {additional_delay:.2f} seconds"
                        )

                        scroll(page, 2)

                    # Переходимо на наступну сторінку
                    page_number += 1
                    pause(2, 4)  # Невелика пауза між сторінками

                browser.close()
                logger.info(
                    f"Scraper finished for link_id={link_id}. Total pages: {page_number}, Total cars: {total_cars_parsed}"
                )

                # Оновлюємо last_processed_at
                db = SessionLocal()
                try:
                    link = db.query(Link).filter(Link.id == link_id).first()
                    if link:
                        link.last_processed_at = datetime.utcnow()
                        db.commit()
                except Exception as e:
                    logger.error(
                        f"Error updating last_processed_at for link_id={link_id}: {e}"
                    )
                finally:
                    db.close()

        except Exception as e:
            logger.exception(f"Error in scraper for link_id={link_id}: {e}")

    # Запускаємо в окремому потоці
    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return thread


def get_all_car_links(parent_link: str) -> list[str]:
    """
    Парсить тільки посилання на всі авто для даного батьківського лінка.
    Повертає список унікальних лінків.
    """
    logger.info("get_all_car_links starting for url=%s", parent_link)
    all_links: list[str] = []

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

        page_number = 0

        while True:
            current_url = update_page_in_url(parent_link, page_number)
            logger.info(f"PAGE {page_number}: Opening {current_url}")

            page.goto(current_url, wait_until="domcontentloaded", timeout=60000)
            pause(2, 4)
            scroll(page)
            move_mouse(page)

            links = get_links(page)

            if not links:
                logger.info(
                    f"PAGE {page_number}: No cars found. Stopping link collector."
                )
                break

            logger.info(f"PAGE {page_number}: Found {len(links)} cars")

            all_links.extend(links)

            page_number += 1
            pause(2, 4)

        browser.close()

    unique_links = list(dict.fromkeys(all_links))
    logger.info(f"Total unique car links collected: {len(unique_links)}")
    return unique_links
