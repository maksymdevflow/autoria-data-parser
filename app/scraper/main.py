import time
import random
import logging
from playwright.sync_api import sync_playwright, Page
from functions.function import save_data_to_db

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


def get_links(page: Page) -> list[str]:
    logger.info("Waiting for search cards")

    try:
        # Чекаємо на картки, але не падаємо якщо їх немає
        page.wait_for_selector("a.product-card", timeout=10000)
    except Exception:
        # Якщо карток немає - повертаємо порожній список
        logger.info("No product cards found on page")
        return []

    pause(1.5, 3)
    scroll(page, 2)

    cards = page.locator("a.product-card")
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
    logger.info("Found %s auto links", len(unique))
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
    year_match = re.search(r'\b(19|20)\d{2}\b', title)
    if year_match:
        result["year"] = int(year_match.group())
    
    # Видаляємо рік з title і беремо перше слово як brand
    title_without_year = re.sub(r'\s*\d{4}\s*', ' ', title).strip()
    parts = title_without_year.split()
    if parts:
        # Беремо перші 1-2 слова як brand (наприклад "Mercedes-Benz" або "DAF")
        brand = parts[0]
        if len(parts) > 1 and parts[1] in ['Benz', 'Actros', 'Axor', 'Atego']:
            brand = f"{parts[0]}-{parts[1]}"
        result["brand"] = brand
    
    return result


def extract_car_info_from_values(car_values: dict) -> dict:
    """
    Витягує fuel_type, transmission, color з car_values.
    """
    result = {
        "fuel_type": "Unknown",
        "transmission": "Unknown",
        "color": None
    }
    
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
    
    Args:
        page: Playwright page object
        car_link: Персональний лінк авто
        parent_link: Батьківський лінк (той що для парсингу)
    """
    logger.info("OPEN %s", car_link)

    page.goto(car_link, wait_until="domcontentloaded", timeout=60000)

    pause(2, 4)
    scroll(page, 2)
    move_mouse(page)

    page.wait_for_selector("#sidePrice strong", timeout=20000)
    page.wait_for_selector("#descList", timeout=20000)

    try:
        price = page.locator("#sidePrice strong").text_content().strip()
        title = page.locator('xpath=//*[@id="sideTitleTitle"]/span').text_content().strip()
        mileage = page.locator("#basicInfoTableMainInfo0 span").text_content().strip()
        location = page.locator("#basicInfoTableMainInfoGeo span").text_content().strip()
        description = page.locator(
            'xpath=//*[@id="descCharacteristicsValue"]/span'
        ).text_content().strip()

    except Exception as e:
        logger.error("FAILED base fields: %s", e)
        # Зберігаємо запис з FAILED статусом
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
            )
        except Exception:
            pass
        return

    car_values = extract_car_values(page)

    if not car_values:
        logger.error("car_values EMPTY - saving with FAILED status")
        # Зберігаємо запис з FAILED статусом
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
            )
        except Exception:
            pass
        return

    # Парсимо title для brand та year
    title_info = parse_title(title)
    
    # Витягуємо інформацію з car_values
    car_info = extract_car_info_from_values(car_values)
    
    data = {
        "price": price,
        "full_title": title,
        "mileage": mileage,
        "location": location,
        "description": description,
        "car_values": car_values,
        # Додаємо витягнуті дані
        "brand": title_info["brand"],
        "year": title_info["year"],
        "fuel_type": car_info["fuel_type"],
        "transmission": car_info["transmission"],
        "color": car_info["color"],
    }
    
    logger.warning("SAVE DATA car_values=%s", data["car_values"])
    logger.info("Parsed data: brand=%s, year=%s, fuel_type=%s, transmission=%s", 
                data["brand"], data["year"], data["fuel_type"], data["transmission"])
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
