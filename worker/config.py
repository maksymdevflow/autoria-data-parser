from celery import Celery
from celery.schedules import crontab
from functions.function import check_period_link_to_process
from app.scraper.main import get_data_by_link
from playwright.sync_api import sync_playwright

celery_app = Celery(
    "autoria",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/1",
)

celery_app.conf.timezone = "UTC"


@celery_app.task(bind=True, autoretry_for=(Exception,), retry_kwargs={"max_retries": 3, "countdown": 60})
def scrape_link(self, url: str):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            return get_data_by_link(page, url)
        finally:
            browser.close()


@celery_app.task
def check_links():
    process_links = check_period_link_to_process()
    for link in process_links:
        scrape_link.delay(link.link)


celery_app.conf.beat_schedule = {
    "check-links-every-minute": {
        "task": "worker.config.check_links",
        "schedule": crontab(minute="*/1"),
    },
}
