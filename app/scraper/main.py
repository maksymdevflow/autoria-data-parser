import sys 
import re
import csv
import time
from concurrent.futures import ThreadPoolExecutor
from playwright.sync_api import sync_playwright, Playwright
from constants import cat_list
test_link="https://auto.ria.com/uk/auto_man_tgl_37774970.html"

def run(playwright: Playwright):
    chromium = playwright.chromium
    browser = chromium.launch()
    page = browser.new_page()

    page.goto("https://auto.ria.com/uk/search/?search_type=1&bodystyle[0]=198&bodystyle[1]=197&bodystyle[2]=153&owner=1035383&page=0&limit=20")

    page.wait_for_load_state("networkidle")

    links = page.locator('xpath=//*[@id="items"]//a')
    all_hrefs = []
    for i in range(links.count()):
        href = links.nth(i).get_attribute("href")
        if href: 
            all_hrefs.append(href)

    get_data_by_link(page=page, link=test_link)
    browser.close()

def get_list_of_link(page):
    links = page.locator('xpath=//*[@id="items"]//a')
    all_hrefs = []
    for i in range(links.count()):
        href = links.nth(i).get_attribute("href")
        if href: 
            all_hrefs.append(href)
    return all_hrefs

def get_data_by_link(page, link):
    page.goto(link)
    page.wait_for_load_state("networkidle")

    price = page.locator('xpath=//*[@id="sidePrice"]/strong').text_content()
    full_title = page.locator('xpath=//*[@id="sideTitleTitle"]/span').text_content()
    millage = page.locator('xpath=//*[@id="basicInfoTableMainInfo0"]/span').text_content()
    car_value = page.locator('xpath=//*[@id="descCharacteristicsValue"]/span').text_content()
    
    cat = page.locator('xpath=//*[@id="descList"]//div')
    for i in range(cat.count()):
        div_id=cat.nth(i).get_attribute("id")
        span = page.locator(f'xpath=//*[@id="{div_id}"]/span')
        if span.count() > 0:
            span_text = span.text_content()
            print(f"Div id: {div_id}, span text: {span_text}")
        else:
            print(f"Div id: {div_id} не має span")
        print(div_id)

    print(cat)

def process_data():
    pass

def save_data_to_db():
    pass


with sync_playwright() as playwright:
    run(playwright)

