"""books.toscrape.com: pagination + detail pages + concurrency.

Flow:
  1. walk the catalogue pages following the "next" link, collecting product URLs;
  2. open every product page (in parallel threads, still rate limited by the Fetcher);
  3. parse each page into a clean record with typed fields.
"""
from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin

from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

BASE = "https://books.toscrape.com/"
RATINGS = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}


def _money(text: str) -> float:
    """'£51.77' or 'Â£51.77' (bad encoding) -> 51.77"""
    m = re.search(r"(\d+(?:\.\d+)?)", text.replace(",", ""))
    if not m:
        raise ValueError(f"no price in {text!r}")
    return float(m.group(1))


def parse_listing(html: str, page_url: str) -> tuple[list[str], str | None]:
    """Return (absolute product URLs on this page, absolute URL of next page or None)."""
    soup = BeautifulSoup(html, "lxml")
    links = [urljoin(page_url, a["href"]) for a in soup.select("article.product_pod h3 a")]
    nxt = soup.select_one("li.next a")
    return links, (urljoin(page_url, nxt["href"]) if nxt else None)


def parse_book(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    main = soup.select_one(".product_main")
    table = {tr.th.get_text(strip=True): tr.td.get_text(strip=True)
             for tr in soup.select("table.table-striped tr")}

    rating_cls = [c for c in main.select_one(".star-rating")["class"] if c != "star-rating"]
    avail_txt = main.select_one(".availability").get_text(" ", strip=True)
    stock = re.search(r"\((\d+) available\)", avail_txt)

    crumbs = [li.get_text(strip=True) for li in soup.select(".breadcrumb li")]
    desc_anchor = soup.select_one("#product_description")
    desc = desc_anchor.find_next_sibling("p").get_text(strip=True) if desc_anchor else ""
    img = soup.select_one("#product_gallery img")

    return {
        "upc": table.get("UPC", ""),
        "title": main.h1.get_text(strip=True),
        "category": crumbs[2] if len(crumbs) >= 4 else "",
        "price_incl_tax": _money(table.get("Price (incl. tax)", "")),
        "price_excl_tax": _money(table.get("Price (excl. tax)", "")),
        "tax": _money(table.get("Tax", "0")),
        "in_stock": int(stock.group(1)) if stock else 0,
        "rating": RATINGS.get(rating_cls[0], 0) if rating_cls else 0,
        "reviews": int(table.get("Number of reviews", "0") or 0),
        "description": desc,
        "image_url": urljoin(url, img["src"]) if img else "",
        "url": url,
    }


def scrape(fetcher, max_pages: int | None = None, workers: int = 4, start_url: str = BASE) -> list[dict]:
    # 1. listing pages
    product_urls: list[str] = []
    url, page = start_url, 0
    while url and (max_pages is None or page < max_pages):
        links, url = parse_listing(fetcher.get_text(url), url)
        product_urls.extend(links)
        page += 1
        log.info("listing page %d: %d products (total %d)", page, len(links), len(product_urls))

    # 2+3. detail pages in parallel; failures are logged and skipped, never fatal
    records, failed = [], []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(fetcher.get_text, u): u for u in product_urls}
        total = len(futures)
        for done, fut in enumerate(as_completed(futures), 1):
            if done % 50 == 0 or done == total:
                log.info("details %d/%d (%d%%)", done, total, 100 * done // total)
            u = futures[fut]
            try:
                records.append(parse_book(fut.result(), u))
            except Exception as e:                   # noqa: BLE001 - keep the crawl alive
                failed.append(u)
                log.warning("failed %s: %s", u, e)
    if failed:
        log.warning("%d product pages failed", len(failed))
    records.sort(key=lambda r: r["url"])
    return records
