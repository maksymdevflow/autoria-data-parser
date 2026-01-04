import sys
import re
import csv
import time
import os
import uuid
import requests
import numpy as np
import cv2
from concurrent.futures import ThreadPoolExecutor
from playwright.sync_api import sync_playwright, Playwright
from .constants import cat_list
from functions.function import *
test_link = "https://auto.ria.com/uk/search/?search_type=1&bodystyle[0]=198&bodystyle[1]=197&bodystyle[2]=153&owner=1035383&page=0&limit=20"
import logging
from playwright.sync_api import Playwright, TimeoutError as PlaywrightTimeoutError, Page

logger = logging.getLogger(__name__)
import random


def human_pause(min_s=0.5, max_s=1.5):
    time.sleep(random.uniform(min_s, max_s))


def human_scroll(page, steps=3):
    for _ in range(steps):
        page.mouse.wheel(0, random.randint(300, 700))
        human_pause(0.3, 0.8)


def human_move_mouse(page):
    x = random.randint(100, 800)
    y = random.randint(100, 600)
    page.mouse.move(x, y, steps=random.randint(10, 25))


class OwnerCars:
    def __init__(self):
        pass


def run(playwright: Playwright):
    chromium = playwright.chromium

    browser = chromium.launch(
        headless=False,      # ❗ виглядати як реальний користувач
        slow_mo=50           # ❗ уповільнення дій
    )

    context = browser.new_context(
        locale="uk-UA",
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1366, "height": 768},
    )

    page = context.new_page()

    SEARCH_URL = (
        "https://auto.ria.com/uk/search/"
        "?search_type=1&bodystyle[0]=198&bodystyle[1]=197&bodystyle[2]=153"
        "&owner=1035383&page=0&limit=20"
    )

    print("🌐 Відкриваю search page...")
    page.goto(
        SEARCH_URL,
        wait_until="domcontentloaded",
        timeout=60000
    )

    # 🧠 дати сторінці «ожити»
    human_pause(2, 4)
    human_scroll(page)
    human_move_mouse(page)

    # 🍪 cookies
    accept_cookies(page)

    human_pause(2, 3)

    # ===========================
    # 1️⃣ список авто
    # ===========================
    auto_links = get_auto_links_from_search(page)

    if not auto_links:
        print("❌ Авто не знайдені")
        return

    # ===========================
    # 2️⃣ парсинг авто
    # ===========================
    for idx, auto_url in enumerate(auto_links, start=1):
        print(f"\n🚗 [{idx}/{len(auto_links)}] {auto_url}")

        try:
            human_pause(1.5, 3.5)
            human_move_mouse(page)

            data = get_data_by_link(page, auto_url)

            if not data:
                print("⚠️ Немає даних")
                continue

        except Exception as e:
            print(f"❌ Помилка: {e}")
            continue

        human_pause(1.5, 2.5)

    print("\n✅ Парсинг завершено")
    input("⏸ Натисни Enter щоб закрити браузер...")

    browser.close()
# def get_list_of_link(page):
#     links = page.locator('xpath=//*[@id="items"]//a')
#     all_hrefs = []
#     for i in range(links.count()):
#         href = links.nth(i).get_attribute("href")
#         if href:
#             all_hrefs.append(href)
#     return all_hrefs

def get_auto_links_from_search(page) -> list[str]:
    """
    Забирає посилання на всі авто зі search page AutoRia
    """
    print("🔍 Очікую появу карток авто...")

    page.wait_for_selector(
        'a.product-card',
        timeout=20000
    )

    cards = page.locator('a.product-card')
    count = cards.count()

    print(f"Знайдено карток: {count}")

    links = []

    for i in range(count):
        href = cards.nth(i).get_attribute("href")

        if not href:
            continue

        if href.startswith("/"):
            href = "https://auto.ria.com" + href

        if "/auto_" in href:
            links.append(href)

    unique_links = list(dict.fromkeys(links))

    print(f"✅ Валідних авто-лінків: {len(unique_links)}")

    for link in unique_links[:3]:
        print("  →", link)

    return unique_links


def accept_cookies(page: Page) -> bool:
    """
    Людський та надійний клік cookie consent
    """
    try:
        # ⏳ дати банеру зʼявитись
        human_pause(2.0, 3.5)
        human_move_mouse(page)

        clicked = page.evaluate(
            """
            () => {
                const btn =
                    document.querySelector('button.fc-button.fc-cta-do-not-consent') ||
                    document.evaluate(
                        "/html/body/div[2]/div[2]/div[2]/div[2]/div[2]/button[2]",
                        document,
                        null,
                        XPathResult.FIRST_ORDERED_NODE_TYPE,
                        null
                    ).singleNodeValue;

                if (btn) {
                    btn.click();
                    return true;
                }
                return false;
            }
            """
        )

        if clicked:
            print("✅ Cookie consent clicked (human-like)")
            return True

    except Exception as e:
        print("❌ Cookie click failed:", e)

    print("ℹ Cookie banner not found")
    return False

def get_data_by_link(page, link):
    page.goto(
        link,
        wait_until="domcontentloaded",
        timeout=60000
    )
    human_pause(2.0, 4.0)
    human_scroll(page, steps=2)
    human_move_mouse(page)
    page.wait_for_load_state("networkidle")

    price = page.locator('xpath=//*[@id="sidePrice"]/strong').text_content()
    print(price, "PRICE")
    full_title = page.locator('xpath=//*[@id="sideTitleTitle"]/span').text_content()
    print(full_title, "FULL TITLE")
    millage = page.locator(
        'xpath=//*[@id="basicInfoTableMainInfo0"]/span'
    ).text_content()
    print(millage, "MILLAGE")
    car_value = page.locator(
        'xpath=//*[@id="descCharacteristicsValue"]/span'
    ).text_content()
    print(car_value, "CAR VALUE")
    description = page.locator('xpath=//*[@id="col"]/div[6]/div/span').text_content()
    print(description, "DESCRIPTION")
    owner = page.locator('xpath=//*[@id="sellerInfoUserName"]/span').text_content()
    print(owner, "OWNER")
    location = page.locator(
        'xpath=//*[@id="basicInfoTableMainInfoGeo"]/span'
    ).text_content()
    print(location, "LOCATION")

    car_link = link
    print(car_link, "CAR LINK")

    cat = page.locator('xpath=//*[@id="descList"]//div')

    cat_dict = {}
    try:
        for i in range(cat.count()):
            div_id = cat.nth(i).get_attribute("id")
            span = page.locator(f'xpath=//*[@id="{div_id}"]/span')
            if span.count() > 0:
                span_text = span.text_content()
                cat_dict[div_id] = span_text
    except Exception as e:
        logger.error(f"Error getting cat data: {e}")
        return None
    images = get_images_by_width(page=page, url=link)
    print(images, "IMAGES")
    data = process_data(
        price,
        full_title,
        millage,
        car_value,
        description,
        owner,
        location,
        car_link,
        cat_dict,
        images,
    )

    save_data_to_db(data)
    return data

def download_as_array(url: str):
    """Downloads image from URL and returns as numpy array."""
    try:
        time.sleep(1)
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        img_arr = np.frombuffer(r.content, dtype=np.uint8)
        return cv2.imdecode(img_arr, cv2.IMREAD_COLOR)
    except Exception as e:
        logger.error(f"Failed to download {url}: {e}")
        return None


def generate_formatted_data(
    image, out_path: str, template_path: str, quality: int = 85
) -> bool:
    """Crops image using template matching and saves to output path."""
    if not os.path.exists(template_path):
        logger.error(f"Template file '{template_path}' not found")
        return False

    template = cv2.imread(template_path)
    h, w = template.shape[:2]
    res = cv2.matchTemplate(image, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)

    if max_val >= 0.8:
        y_crop = max_loc[1] + h
        cropped = image[y_crop:, :]
        cv2.imwrite(out_path, cropped, [cv2.IMWRITE_JPEG_QUALITY, quality])
        logger.debug(f"Processed {os.path.basename(out_path)}")
        return True
    else:
        logger.debug("Logo not found or match too low")
        return False


def process_images(
    images: list, template_path: str = None, output_base: str = "car_images"
) -> str:
    """Processes images by cropping and saves to UUID folder, returns folder name."""
    if not images:
        logger.warning("No images to process")
        return ""

    if template_path is None:
        template_path = os.path.join(os.path.dirname(__file__), "icon_test.png")

    folder_name = str(uuid.uuid4())
    output_dir = os.path.join(output_base, folder_name)

    try:
        os.makedirs(output_dir, exist_ok=True)
        logger.info(f"Created folder: '{output_dir}'")
    except Exception as e:
        logger.error(f"Error creating folder '{output_dir}': {e}")
        return ""

    processed_count = 0
    for i, url in enumerate(images, 1):
        try:
            img = download_as_array(url)
            if img is None:
                continue

            out_file = f"car_{i}_no_logo.jpg"
            out_path = os.path.join(output_dir, out_file)

            if generate_formatted_data(img, out_path, template_path):
                processed_count += 1
        except Exception as e:
            logger.error(f"Error processing {url}: {e}")

    if processed_count:
        logger.info(f"Processed {processed_count} images in '{output_dir}'")
        return folder_name
    else:
        logger.warning("No images were processed")
        return ""


def process_data(
    price: int,
    full_title: str,
    millage: int,
    car_value: str,
    description: str,
    owner: str,
    location: str,
    car_link: str,
    cat_dict: dict,
    images: list,
) -> dict:

    formatted_cat_dict = {}
    for k, v in cat_dict.items():
        if k in cat_list:
            formatted_cat_dict[k] = v

    path_to_images = process_images(images)

    auto_params = {
        "link": car_link,
        "price": price,
        "full_title": full_title,
        "millage": millage,
        "car_value": car_value,
        "description": description,
        "owner": owner,
        "location": location,
        "car_link": car_link,
        "cat_dict": formatted_cat_dict,
        "path_to_images": path_to_images,
    }

    print(auto_params, "AUTO PARAMS")

    return auto_params


def get_images_by_width(url: str, page=None, target_width: str = "100%") -> list:
    """Extracts image URLs from a page using Playwright."""
    browser = None
    playwright_instance = None
    should_close_browser = False

    try:
        if page is None:
            playwright_instance = sync_playwright().start()
            browser = playwright_instance.chromium.launch()
            page = browser.new_page()
            should_close_browser = True

        if url:
            page.goto(url)
            page.wait_for_load_state("networkidle")
    except Exception as e:
        logger.error(f"Error loading page {url}: {e}")
        if browser:
            browser.close()
        if playwright_instance:
            playwright_instance.stop()
        return []

    required_phrase = ""
    try:
        phrase_locator = page.locator(
            "xpath=/html/body/div/main/div[1]/div[3]/div[2]/div[1]/div[1]/div[1]/span"
        )
        if phrase_locator.count() > 0:
            required_phrase = (phrase_locator.first.text_content() or "").strip()
    except Exception as e:
        logger.debug(f"Failed to extract phrase from XPath: {e}")

    image_urls = []

    try:
        if required_phrase:
            containers = page.locator('li[style*="width:100%"] picture img')
        else:
            containers = page.locator(
                'li[style*="width:100%"] picture img, li[style*="width:100%"] picture source'
            )

        container_count = containers.count()

        if container_count == 0:
            containers = page.locator(
                'li[style*="width:100%"] img, li[style*="width:100%"] source'
            )
            container_count = containers.count()

        if container_count == 0:
            containers = page.locator("img, source")
            container_count = containers.count()

        for i in range(container_count):
            try:
                element = containers.nth(i)

                src = (
                    element.get_attribute("src")
                    or element.get_attribute("data-src")
                    or element.get_attribute("srcset")
                )
                if not src:
                    continue

                if "," in src:
                    src = src.split(",")[0].strip().split(" ")[0]

                if required_phrase:
                    title_attr = (
                        element.get_attribute("title")
                        or element.get_attribute("alt")
                        or ""
                    ).strip()
                    if (
                        not title_attr
                        or required_phrase.lower() not in title_attr.lower()
                    ):
                        continue

                if ("riastatic.com" in src) and ("/photosnew/auto/photo/" in src):
                    hd_src = re.sub(r"(\d+)[a-z]+\.(webp|jpg)$", r"\1hd.jpg", src)
                    image_urls.append(hd_src)
            except Exception as e:
                logger.debug(f"Error processing element {i}: {e}")
                continue

    except Exception as e:
        logger.error(f"Error searching for images: {e}")
        if browser:
            browser.close()
        if playwright_instance:
            playwright_instance.stop()
        return []
    finally:
        if browser and should_close_browser:
            browser.close()
        if playwright_instance and should_close_browser:
            playwright_instance.stop()

    image_urls = list(set(image_urls))
    logger.info(f"Found {len(image_urls)} images")
    return image_urls


def get_list_of_pages(page) -> int:
    """Returns the number of pages by counting li elements in pagination."""
    try:
        pagination = page.locator('xpath=//*[@id="items"]/div[3]/nav/ul/li')
        page_count = pagination.count()
        return page_count if page_count > 0 else 1
    except Exception as e:
        logger.error(f"Error getting page count: {e}")
        return 1

def next_page(pre_page: str, next_page: str):
    pass

with sync_playwright() as playwright:
    run(playwright)