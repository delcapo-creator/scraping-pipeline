"""scrapethissite.com - Countries of the World: one page, 250 countries."""

from __future__ import annotations

from bs4 import BeautifulSoup

BASE = "https://www.scrapethissite.com/pages/simple/"


def parse_page(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    rows = []
    for c in soup.select("div.country"):  # كل دولة
        capital = c.select_one("span.country-capital").get_text(strip=True)
        rows.append(
            {
                "name": c.select_one("h3.country-name").get_text(strip=True),
                "capital": "" if capital == "None" else capital,
                "population": int(
                    c.select_one("span.country-population").get_text(strip=True)
                ),
                "area_km2": float(
                    c.select_one("span.country-area").get_text(strip=True)
                ),
            }
        )
    return rows


def scrape(fetcher) -> list[dict]:
    return parse_page(fetcher.get_text(BASE))  # صفحة واحدة، بدون ترقيم
