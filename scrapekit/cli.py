"""Command line:  python -m scrapekit books|quotes [options]"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from .export import write_all
from .http import Fetcher
from .sites import books, quotes
from .validate import BOOK_RULES, QUOTE_RULES, dedupe, validate


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="scrapekit", description="Polite, validated web scraping pipeline.")
    ap.add_argument("site", choices=["books", "quotes"])
    ap.add_argument("--mode", default="api", choices=["html", "js", "api", "browser"],
                    help="quotes only: how to get the data (default: api)")
    ap.add_argument("--max-pages", type=int, default=None, help="stop after N listing pages")
    ap.add_argument("--workers", type=int, default=4, help="books only: parallel detail-page downloads")
    ap.add_argument("--delay", type=float, default=0.5, help="seconds between requests (rate limit)")
    ap.add_argument("--out", default="data", help="output folder")
    ap.add_argument("--formats", default="csv,json,sqlite", help="comma list of csv,json,sqlite")
    ap.add_argument("--cache", default=".cache", help="HTML cache folder ('' to disable)")
    ap.add_argument("--strict", action="store_true", help="exit code 2 when validation fails")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    fetcher = Fetcher(delay=a.delay, cache_dir=a.cache or None)
    t0 = time.time()

    if a.site == "books":
        rows = books.scrape(fetcher, max_pages=a.max_pages, workers=a.workers)
        key, rules, name = "upc", BOOK_RULES, "books"
    else:
        rows = quotes.scrape(fetcher, mode=a.mode, max_pages=a.max_pages)
        key, rules, name = ("text", "author"), QUOTE_RULES, f"quotes_{a.mode}"

    rep = validate(rows, rules, key)
    print("\n=== validation ===\n" + rep.summary())
    rows = dedupe(rows, key)
    paths = write_all(rows, Path(a.out), name, [f.strip() for f in a.formats.split(",") if f.strip()])

    print(f"\n{len(rows)} rows in {time.time() - t0:.1f}s | "
          f"{fetcher.stats['requests']} requests, {fetcher.stats['cache_hits']} from cache")
    for p in paths:
        print("wrote", p)
    return 2 if (a.strict and not rep.ok) else 0


if __name__ == "__main__":
    sys.exit(main())
