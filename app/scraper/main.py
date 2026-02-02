import time
import random
import logging
import os
import uuid
import re
import requests
import numpy as np
import cv2
from playwright.sync_api import sync_playwright, Page
from functions.function import save_data_to_db, save_failed_car_and_add_to_delete
from database.models import StatusProcessed

# --------------------------------------------------
# LOGGING
# --------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

# --------------------------------------------------
# CONSTANTS
# --------------------------------------------------
SEARCH_URL = (
    "https://auto.ria.com/uk/search/"
    "?search_type=1&bodystyle[0]=198&bodystyle[1]=197"
    "&bodystyle[2]=153&owner=1035383&page=0&limit=20"
)

CAT_LIST = [
    "descEngineEngine",
    "descEcoStandartEcoStandart",
    "descTransmissionTransmission",
    "descDriveTypeDriveType",
    "descColorColor",
    "descConditionerValue",
]


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
            # Затримка 1 секунда між обробкою кожного фото
            if i > 1:
                time.sleep(1)

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
            # Якщо створюємо новий page, завантажуємо сторінку
            if url:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_load_state("networkidle", timeout=30000)
        # Якщо page передано, не завантажуємо сторінку знову (вона вже завантажена в parse_car)
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
                    # Додаємо тільки якщо ще немає в списку (зберігаємо порядок)
                    if hd_src not in image_urls:
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

    # Обмежуємо до 20 фото включно (порядок зберігається)
    image_urls = image_urls[:20]
    logger.info(f"Found {len(image_urls)} images (limited to 20, order preserved)")
    return image_urls


def pause(a=0.7, b=1.8):
    time.sleep(random.uniform(a, b))


def scroll(page: Page, steps=2):
    for _ in range(steps):
        page.mouse.wheel(0, random.randint(300, 700))
        pause(0.4, 0.9)


def move_mouse(page: Page):
    page.mouse.move(
        random.randint(100, 900),
        random.randint(100, 600),
        steps=random.randint(15, 30),
    )


def accept_cookies(page: Page):
    try:
        pause(2, 4)
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
            logger.info("Cookies rejected")
    except Exception:
        pass


# XPath: лише картки авто, що не всередині блоку "В інших категоріях" (InOtherCategoryList)
_CAR_CARDS_XPATH = (
    "//a[contains(@class, 'product-card') and not(ancestor::*[@id='InOtherCategoryList'])]"
)


def get_links(page: Page) -> list[str]:
    logger.info("Waiting for search cards")

    try:
        page.wait_for_selector("a.product-card", timeout=10000)
    except Exception:
        logger.info("No product cards found on page")
        return []

    pause(1.5, 3)
    scroll(page, 2)

    cards = page.locator(f"xpath={_CAR_CARDS_XPATH}")
    links = []

    for i in range(cards.count()):
        href = cards.nth(i).get_attribute("href")
        if not href:
            continue
        if href.startswith("/"):
            href = "https://auto.ria.com" + href
        if "/auto_" in href:
            links.append(href)

    unique = list(dict.fromkeys(links))
    logger.info("Found %s auto links (excluding InOtherCategoryList)", len(unique))
    return unique


def extract_car_values(page: Page) -> dict:
    result = {}

    blocks = page.locator('xpath=//*[@id="descList"]//div')

    for i in range(blocks.count()):
        block = blocks.nth(i)
        block_id = block.get_attribute("id")

        if not block_id:
            continue

        if block_id not in CAT_LIST:
            continue

        span = block.locator("span")
        if span.count() == 0:
            continue

        value = span.first.text_content()
        if value:
            result[block_id] = value.strip()

    logger.info("car_values parsed: %s", result)
    return result


def parse_title(title: str) -> dict:
    """
    Парсить title для витягнення brand та year.
    Приклад: "DAF LF 2018" -> {"brand": "DAF", "year": 2018}
    """
    import re

    result = {"brand": "Unknown", "year": 0}

    if not title:
        return result

    # Шукаємо рік (4 цифри між 1900-2100)
    year_match = re.search(r"\b(19|20)\d{2}\b", title)
    if year_match:
        result["year"] = int(year_match.group())

    # Видаляємо рік з title і беремо перше слово як brand
    title_without_year = re.sub(r"\s*\d{4}\s*", " ", title).strip()
    parts = title_without_year.split()
    if parts:
        # Беремо перші 1-2 слова як brand (наприклад "Mercedes-Benz" або "DAF")
        brand = parts[0]
        if len(parts) > 1 and parts[1] in ["Benz", "Actros", "Axor", "Atego"]:
            brand = f"{parts[0]}-{parts[1]}"
        result["brand"] = brand

    return result


def parse_brand_and_model(full_title: str) -> dict:
    """
    Парсить повну назву з basicInfoTitle для витягнення brand та model.
    Приклад: "MAN TGL 2018" -> {"brand": "MAN", "model": "TGL", "year": 2018}
    """
    import re

    result = {"brand": "Unknown", "model": None, "year": 0}

    if not full_title:
        return result

    # Шукаємо рік (4 цифри між 1900-2100)
    year_match = re.search(r"\b(19|20)\d{2}\b", full_title)
    if year_match:
        result["year"] = int(year_match.group())

    # Видаляємо рік з назви
    title_without_year = re.sub(r"\s*\d{4}\s*", " ", full_title).strip()
    parts = title_without_year.split()

    if len(parts) >= 1:
        result["brand"] = parts[0]  # Перше слово - марка

    if len(parts) >= 2:
        result["model"] = parts[1]  # Друге слово - модель
    elif len(parts) > 2:
        result["model"] = parts[1]

    # Спеціальний випадок: деякі оголошення можуть мати порядок "Jumper Citroen"
    # (спочатку модель, потім марка). Якщо так, міняємо місцями.
    from functions.constants import format_3_5t_brands, format_3_5t_models

    brand = result["brand"]
    model = result["model"]

    if brand and model:
        brand_names = set(format_3_5t_brands.values())
        # Плоский список усіх назв моделей
        model_names = {
            name for models in format_3_5t_models.values() for name in models.values()
        }

        # Якщо "бренд" більше схожий на модель, а "модель" є відомим брендом – міняємо.
        if (brand in model_names) and (model in brand_names):
            result["brand"], result["model"] = model, brand

    return result


def extract_car_info_from_values(car_values: dict) -> dict:
    """
    Витягує fuel_type, transmission, color з car_values.
    """
    result = {"fuel_type": "Unknown", "transmission": "Unknown", "color": None}

    # Fuel type з descEngineEngine (наприклад "Дизель, 6.7 л")
    engine = car_values.get("descEngineEngine", "")
    if engine:
        if "Дизель" in engine or "Diesel" in engine:
            result["fuel_type"] = "Дизель"
        elif "Бензин" in engine or "Petrol" in engine or "Gasoline" in engine:
            result["fuel_type"] = "Бензин"
        elif "Газ" in engine or "Gas" in engine:
            result["fuel_type"] = "Газ"
        elif "Електричний" in engine or "Electric" in engine:
            result["fuel_type"] = "Електричний"

    # Transmission з descTransmissionTransmission
    transmission = car_values.get("descTransmissionTransmission", "")
    if transmission:
        result["transmission"] = transmission.strip()

    # Color з descColorColor
    color = car_values.get("descColorColor", "")
    if color:
        result["color"] = color.strip()

    return result


def parse_car(page: Page, car_link: str, parent_link: str):
    """
    Парсить дані про авто за персональним лінком.
    При помилці (таймаут, відсутній #descList тощо) ставить FAILED і додає в links_to_delete.
    """
    logger.info("OPEN %s", car_link)
    try:
        page.goto(car_link, wait_until="domcontentloaded", timeout=60000)
        pause(2, 4)
        scroll(page, 2)
        move_mouse(page)
        page.wait_for_selector("#sidePrice strong", timeout=20000)
        page.wait_for_selector("#descList", timeout=20000)
    except Exception as e:
        logger.error("Parse failed (goto/wait): %s", e)
        save_failed_car_and_add_to_delete(parent_link, car_link)
        return

    try:
        price = page.locator("#sidePrice strong").text_content().strip()
        title = (
            page.locator('xpath=//*[@id="sideTitleTitle"]/span').text_content().strip()
        )
        # Парсимо повну назву з basicInfoTitle для brand та model
        full_title_elem = page.locator('xpath=//*[@id="basicInfoTitle"]/h1')
        full_title = ""
        if full_title_elem.count() > 0:
            full_title = full_title_elem.first.text_content().strip()
        mileage = page.locator("#basicInfoTableMainInfo0 span").text_content().strip()
        location = (
            page.locator("#basicInfoTableMainInfoGeo span").text_content().strip()
        )
        description = (
            page.locator('xpath=//*[@id="descCharacteristicsValue"]/span')
            .text_content()
            .strip()
        )

        # Парсимо детальний опис (може бути або не бути)
        # Коректний XPath з сторінки:
        # /html/body/div/main/div[1]/div[2]/div[1]/div[6]/div[1]/span/text()
        full_description = None
        try:
            full_desc_locator = page.locator(
                "xpath=/html/body/div/main/div[1]/div[2]/div[1]/div[6]/div[1]/span"
            )
            if full_desc_locator.count() > 0:
                # Беремо всі текстові частини і об'єднуємо в один багаторядковий текст
                parts = [
                    t.strip()
                    for t in full_desc_locator.all_text_contents()
                    if t and t.strip()
                ]
                if parts:
                    full_description = "\n".join(parts)
        except Exception:
            # Якщо елементу немає або структура інша – залишаємо None
            full_description = None

    except Exception as e:
        logger.error("FAILED base fields: %s", e)
        try:
            save_data_to_db(
                {
                    "price": "0",
                    "full_title": "",
                    "mileage": "0",
                    "location": "",
                    "description": f"Failed to parse: {str(e)}",
                    "car_values": {},
                    "brand": "Unknown",
                    "year": 0,
                    "fuel_type": "Unknown",
                    "transmission": "Unknown",
                    "color": None,
                },
                parent_link,
                car_link,
                processed_status=StatusProcessed.FAILED,
            )
        except Exception:
            pass
        return

    car_values = extract_car_values(page)

    if not car_values:
        logger.error("car_values EMPTY - saving with FAILED status")
        try:
            save_data_to_db(
                {
                    "price": price if "price" in locals() else "0",
                    "full_title": title if "title" in locals() else "",
                    "mileage": mileage if "mileage" in locals() else "0",
                    "location": location if "location" in locals() else "",
                    "description": (
                        description
                        if "description" in locals()
                        else "car_values is empty"
                    ),
                    "car_values": {},
                    "brand": "Unknown",
                    "year": 0,
                    "fuel_type": "Unknown",
                    "transmission": "Unknown",
                    "color": None,
                },
                parent_link,
                car_link,
                processed_status=StatusProcessed.FAILED,
            )
        except Exception:
            pass
        return

    # Парсимо title для brand та year (fallback)
    title_info = parse_title(title)

    # Парсимо повну назву з basicInfoTitle для brand, model та year
    brand_model_info = {"brand": "Unknown", "model": None, "year": 0}
    if "full_title" in locals() and full_title:
        brand_model_info = parse_brand_and_model(full_title)
        # Якщо не знайшли brand з full_title, використовуємо з title
        if brand_model_info["brand"] == "Unknown":
            brand_model_info["brand"] = title_info["brand"]
        # Якщо не знайшли year з full_title, використовуємо з title
        if brand_model_info["year"] == 0:
            brand_model_info["year"] = title_info["year"]
    else:
        # Якщо full_title не знайдено, використовуємо title_info
        brand_model_info = title_info
        brand_model_info["model"] = None

    # Витягуємо інформацію з car_values
    car_info = extract_car_info_from_values(car_values)

    # Отримуємо зображення зі сторінки
    images = get_images_by_width(car_link, page=page)

    # Обробляємо зображення
    path_to_images = ""
    if images:
        path_to_images = process_images(images)
        logger.info(f"Processed {len(images)} images, folder: {path_to_images}")

    data = {
        "price": price,
        "full_title": title,
        "mileage": mileage,
        "location": location,
        "description": description,
        "full_description": full_description
        if "full_description" in locals()
        else None,
        "car_values": car_values,
        # Додаємо витягнуті дані
        "brand": brand_model_info["brand"],
        "model": brand_model_info["model"],
        "year": brand_model_info["year"],
        "fuel_type": car_info["fuel_type"],
        "transmission": car_info["transmission"],
        "color": car_info["color"],
        # Додаємо шлях до оброблених зображень
        "path_to_images": path_to_images,
    }

    logger.warning("SAVE DATA car_values=%s", data["car_values"])
    logger.info(
        "Parsed data: brand=%s, year=%s, fuel_type=%s, transmission=%s",
        data["brand"],
        data["year"],
        data["fuel_type"],
        data["transmission"],
    )
    save_data_to_db(data, parent_link, car_link)
    logger.info("SAVED %s", car_link)


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=40)
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
        page.goto(SEARCH_URL, wait_until="domcontentloaded", timeout=60000)

        pause(2, 4)
        scroll(page)
        move_mouse(page)

        accept_cookies(page)
        pause(2, 3)

        links = get_links(page)

        for i, car_link in enumerate(links, 1):
            logger.info("CAR %s/%s", i, len(links))
            try:
                parse_car(page, car_link, SEARCH_URL)
            except Exception as e:
                logger.exception("CRASH on %s: %s", car_link, e)

            pause(3, 6)
            scroll(page, random.randint(1, 3))

            if i % random.randint(5, 7) == 0:
                logger.info("Taking a break")
                pause(15, 25)

        input("Press Enter to exit")
        browser.close()


if __name__ == "__main__":
    run()
