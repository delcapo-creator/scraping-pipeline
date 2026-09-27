"""scrapethissite.com - Hockey Teams: an HTML table + pagination + search.

How the selectors were found (Chrome -> right click a cell -> Inspect):
  every team is one row           <tr class="team">
  every cell has its own class    <td class="name">, "year", "wins", "losses",
                                  "ot-losses", "pct", "gf", "ga", "diff"
  the next page link              <a aria-label="Next" href="?page_num=2">
  search is a URL parameter       ?q=boston
"""
from __future__ import annotations

import logging
from urllib.parse import urlencode, urljoin

from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

BASE = "https://www.scrapethissite.com/pages/forms/"


def _int(text: str) -> int | None:
    text = text.strip()
    return int(text) if text else None          # "OT Losses" is empty for older seasons


def parse_page(html: str, page_url: str) -> tuple[list[dict], str | None]:
    soup = BeautifulSoup(html, "lxml")
    rows = []
    for tr in soup.select("tr.team"):
        cell = lambda cls: tr.select_one(f"td.{cls}").get_text(strip=True)   # noqa: E731
        rows.append({
            "team": cell("name"),
            "year": int(cell("year")),
            "wins": int(cell("wins")),
            "losses": int(cell("losses")),
            "ot_losses": _int(cell("ot-losses")),
            "win_pct": float(cell("pct")),
            "goals_for": int(cell("gf")),
            "goals_against": int(cell("ga")),
            "goal_diff": int(cell("diff")),
        })
    nxt = soup.select_one('a[aria-label="Next"]')
    return rows, (urljoin(page_url, nxt["href"]) if nxt else None)


def scrape(fetcher, query: str = "", max_pages: int | None = None, per_page: int = 100) -> list[dict]:
    params = {"page_num": 1, "per_page": per_page}
    if query:
        params["q"] = query
    url, page, rows = f"{BASE}?{urlencode(params)}", 0, []
    while url and (max_pages is None or page < max_pages):
        recs, url = parse_page(fetcher.get_text(url), url)
        rows += recs
        page += 1
        log.info("page %d: %d teams (total %d)", page, len(recs), len(rows))
    return rows
