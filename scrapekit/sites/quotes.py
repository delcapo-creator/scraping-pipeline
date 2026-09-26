"""quotes.toscrape.com: the same data, four ways to get it.

  html    - classic server-rendered HTML + "Next" pagination (BeautifulSoup)
  js      - page built by JavaScript; the data is embedded in a <script> as JSON,
            so we extract it with a regex instead of launching a browser
  api     - the infinite-scroll page (/scroll) loads JSON from /api/quotes?page=N;
            calling that API directly is the fastest and most robust option
  browser - render /js/ in a real headless browser (Playwright) for sites where
            the data is NOT available anywhere except the rendered DOM

The lesson: before reaching for a browser, open DevTools -> Network and look for
the JSON the page itself downloads.
"""
from __future__ import annotations

import json
import logging
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

BASE = "https://quotes.toscrape.com/"
QUOTE_CHARS = "“”\"'"


def _clean(text: str) -> str:
    return text.strip().strip(QUOTE_CHARS).strip()


def _record(text: str, author: str, tags: list[str], author_url: str = "") -> dict:
    return {"text": _clean(text), "author": author.strip(), "tags": sorted(tags), "author_url": author_url}


# ---------------------------------------------------------------- html
def parse_html_page(html: str, page_url: str) -> tuple[list[dict], str | None]:
    soup = BeautifulSoup(html, "lxml")
    out = []
    for q in soup.select("div.quote"):
        about = q.select_one("span a")
        out.append(_record(
            q.select_one("span.text").get_text(),
            q.select_one("small.author").get_text(),
            [t.get_text(strip=True) for t in q.select("a.tag")],
            urljoin(page_url, about["href"]) if about else "",
        ))
    nxt = soup.select_one("li.next a")
    return out, (urljoin(page_url, nxt["href"]) if nxt else None)


# ---------------------------------------------------------------- js (embedded JSON)
_DATA_RE = re.compile(r"var\s+data\s*=\s*(\[.*?\]);", re.S)


def parse_js_page(html: str, page_url: str) -> tuple[list[dict], str | None]:
    m = _DATA_RE.search(html)
    if not m:
        raise ValueError("embedded `var data = [...]` not found - page layout changed?")
    items = json.loads(m.group(1))
    out = [_record(i["text"], i["author"]["name"], i.get("tags", []),
                   urljoin(BASE, "author/" + i["author"].get("slug", ""))) for i in items]
    nxt = BeautifulSoup(html, "lxml").select_one("li.next a")
    return out, (urljoin(page_url, nxt["href"]) if nxt else None)


# ---------------------------------------------------------------- api
def parse_api_page(payload: dict) -> tuple[list[dict], bool]:
    out = [_record(i["text"], i["author"]["name"], i.get("tags", []),
                   urljoin(BASE, "author/" + i["author"].get("slug", ""))) for i in payload["quotes"]]
    return out, bool(payload.get("has_next"))


# ---------------------------------------------------------------- runners
def _follow(fetcher, start: str, parser, max_pages):
    records, url, page = [], start, 0
    while url and (max_pages is None or page < max_pages):
        recs, url = parser(fetcher.get_text(url), url)
        records += recs
        page += 1
        log.info("page %d: %d quotes", page, len(recs))
    return records


def scrape(fetcher, mode: str = "api", max_pages: int | None = None) -> list[dict]:
    if mode == "html":
        return _follow(fetcher, BASE, parse_html_page, max_pages)
    if mode == "js":
        return _follow(fetcher, urljoin(BASE, "js/"), parse_js_page, max_pages)
    if mode == "api":
        records, page, has_next = [], 1, True
        while has_next and (max_pages is None or page <= max_pages):
            recs, has_next = parse_api_page(fetcher.get_json(urljoin(BASE, f"api/quotes?page={page}")))
            records += recs
            log.info("api page %d: %d quotes", page, len(recs))
            page += 1
        return records
    if mode == "browser":
        return scrape_with_browser(max_pages)
    raise ValueError(f"unknown mode {mode!r}")


def scrape_with_browser(max_pages: int | None = None) -> list[dict]:
    """Render the JavaScript page in headless Chromium. Needs: pip install playwright && playwright install chromium"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise SystemExit("browser mode needs Playwright: pip install playwright && playwright install chromium") from e

    records, url, page_no = [], urljoin(BASE, "js/"), 0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        while url and (max_pages is None or page_no < max_pages):
            page.goto(url)
            page.wait_for_selector("div.quote")      # wait until JavaScript has built the DOM
            recs, url = parse_html_page(page.content(), url)
            records += recs
            page_no += 1
            log.info("browser page %d: %d quotes", page_no, len(recs))
        browser.close()
    return records
