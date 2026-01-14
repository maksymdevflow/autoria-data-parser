import sys 
import re
import csv
import time
from concurrent.futures import ThreadPoolExecutor
from playwright.sync_api import sync_playwright, Playwright
test_link="https://auto.ria.com/uk/auto_man_tgl_37774970.html"

cat_list = [
    'descEngineEngine',
    'descEcoStandartEcoStandart',
    'descTransmission',
    'descDriveType',
    'descColor', 
    'descConditionerValue'
]


def run(playwright: Playwright):
    chromium = playwright.chromium
    browser = chromium.launch()
    page = browser.new_page()

    # Батьківський лінк (той що для парсингу)
    parent_link = "https://auto.ria.com/uk/search/?search_type=1&bodystyle[0]=198&bodystyle[1]=197&bodystyle[2]=153&owner=1035383&page=0&limit=20"
    
    page.goto(parent_link)

    page.wait_for_load_state("networkidle")

    links = page.locator('xpath=//*[@id="items"]//a')
    all_hrefs = []
    for i in range(links.count()):
        href = links.nth(i).get_attribute("href")
        if href: 
            all_hrefs.append(href)

    get_data_by_link(page=page, car_link=test_link, parent_link=parent_link)
    browser.close()

def get_list_of_link(page):
    links = page.locator('xpath=//*[@id="items"]//a')
    all_hrefs = []
    for i in range(links.count()):
        href = links.nth(i).get_attribute("href")
        if href: 
            all_hrefs.append(href)
    return all_hrefs

def get_data_by_link(page, car_link, parent_link):
    """
    Парсить дані про авто за персональним лінком.
    
    Args:
        page: Playwright page object
        car_link: Персональний лінк авто
        parent_link: Батьківський лінк (той що для парсингу)
    """
    page.goto(car_link)
    page.wait_for_load_state("networkidle")

    price = page.locator('xpath=//*[@id="sidePrice"]/strong').text_content()
    full_title = page.locator('xpath=//*[@id="sideTitleTitle"]/span').text_content()
    millage = page.locator('xpath=//*[@id="basicInfoTableMainInfo0"]/span').text_content()
    car_value = page.locator('xpath=//*[@id="descCharacteristicsValue"]/span').text_content()
    
    # Парсимо категорії
    car_values = {}
    cat = page.locator('xpath=//*[@id="descList"]//div')
    for i in range(cat.count()):
        div_id = cat.nth(i).get_attribute("id")
        if div_id and div_id in cat_list:
            span = page.locator(f'xpath=//*[@id="{div_id}"]/span')
            if span.count() > 0:
                span_text = span.text_content()
                car_values[div_id] = span_text.strip()
                print(f"Div id: {div_id}, span text: {span_text}")
    
    # Формуємо дані для збереження
    data = {
        "price": price,
        "full_title": full_title,
        "mileage": millage,
        "description": car_value,
        "car_values": car_values,
    }
    
    # Зберігаємо в БД
    from functions.function import save_data_to_db
    save_data_to_db(data, parent_link, car_link)

def process_data():
    pass


with sync_playwright() as playwright:
    run(playwright)