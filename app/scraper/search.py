from playwright.sync_api import Page
from .human import human_pause, human_scroll

def get_auto_links_from_search(page: Page) -> list[str]:
    page.wait_for_selector("a.product-card", timeout=20000)
    human_pause(1.5, 3)
    human_scroll(page, steps=2)

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

    return list(dict.fromkeys(links))
